# -*- coding: utf-8 -*-
"""
Description: Parser/processor for tbon notation language
Author: Mike Ellis
Copyright 2017 Ellis & Grant, Inc.
"""
#######################################################################
## Pylint Overrides
## pylint: disable=no-self-use, unused-argument
## pylint: disable=blacklisted-name
## pylint: disable=too-many-public-methods
## pylint: disable=too-many-instance-attributes
## pylint: disable=too-many-statements, invalid-name
## pylint: disable=too-many-lines
#######################################################################
import keysigs
from parsimonious.grammar import Grammar

#pylint: disable=anomalous-backslash-in-string
def parse(source):
    """Parse tbon Source"""
    grammar = Grammar(
        """
        score = wsc* music*
        music = (partswitch*  bar+)+ wsc*
        partswitch = "P=" partnum
        wsc = comment / ws+
        comment = ws* ~r"/\*.*?\*/"s ws*
        bar = (wsc* (meta / beat) wsc+)+ barline
        meta = beatspec / key / tempo /
               relativetempo / velocity /
               de_emphasis / channel
        beatspec = "B=" ("2." / "2" / "4." / "4" / "8." / "8")
        key = "K=" keyname
        keyname = ~r"[a-gA-G](@|#)?"
        tempo = "T=" floatnum
        relativetempo = "t=" floatnum
        velocity = "V=" floatnum
        de_emphasis = "D=" floatnum
        channel = "C=" chnum
        partnum = ~r"[1-9][0-9]*"i
        floatnum = ~r"\d*\.?\d+"i
        chnum = "16" / "15" / "14" / "13" / "12" / "11" / "10" / ~r"\d"i
        beat = subbeat+
        barline = "|" / ":"
        extendable = chord / roll / ornament / pitch / rest
        pitch = octave* alteration? pitchname
        chord = chordstart chorditem chorditem* rparen
        chordstart = "("
        chorditem = chordpitch / chordhold / chordrest
        chordpitch = octave* alteration? pitchname
        chordhold = '-'
        chordrest = "_" / "z"
        rparen = ")"
        roll = rollstart pitch pitch+ rparen
        rollstart = "(:"
        ornament = ornamentstart pitch pitch+ rparen
        ornamentstart = "(~"
        subbeat = extendable / hold
        rest = "_" / "z"
        hold = "-"
        octave = octave_up / octave_down
        alteration = doublesharp / sharp / doubleflat / flat / natural
        doublesharp = "𝄪" / "##"
        sharp = "♯" / "#"
        doubleflat = "𝄫" / "@@"
        flat = "♭" / "@"
        natural = "♮" / "%"
        octave_up = "^"
        octave_down = "/"
        pitchname = ~"[a-g1-7]"i
        ws = ~r"\s*"i
        """
        )
    return grammar.parse(source)
#pylint: enable=anomalous-backslash-in-string

## Sub-beat tyoe constants
NOTE = 0
CHORD = 1
ROLL = 2
ORNAMENT = 3

## Dict used to compute new time signatures.
## Maps supported beatspecs to tuples of (mulitplier, denominator)
## Multiplier is applied to the beat count to compute the numerator,
## Thus, B=4. in a bar with 2 beats --> 6/8 time
TIMESIG_LUT = {
    "2.":(3, 4),
    "2":(1, 2),
    "4.":(3, 8),
    "4":(1, 4),
    "8.":(1, 16),
    "8":(1, 8),
}

def time_signature(beatspec, beatcount, index):
    """
    Create a new time signature at index.
    """
    multiplier, numerator = TIMESIG_LUT[beatspec]
    return ('M', index, multiplier*beatcount, numerator)

class MidiPreEvaluator():
    """
    Parses and evaluates a tbon source and produces a time-ordered list of
    sub-beat durations for each beat.
    """
    #pylint: disable=dangerous-default-value
    def __init__(self):
        self.first_tempo = 120
        self.output = []
        self.meta_output = []
        self.beat_map = {1: []}
        self.beat_lengths = []
        self.subbeat_starts = []
        self.subbeat_lengths = []
        self.partstates = {0: self.new_part_state()}
        self.processing_state = self.partstates[0]
        self.current_part = 0
    #pylint: enable=dangerous-default-value

    def eval(self, source, verbosity=2):
        """Evaluate tbon source"""
        node = parse(source) if isinstance(source, str) else source
        method = getattr(self, node.expr_name, lambda node, children: children)
        ## Recursively evaluate subtree
        method(node, [self.eval(n, verbosity) for n in node])
        self.show_progress(node, verbosity)
        return self.output

    def show_progress(self, node, verbosity):
        """ Call this *after* the node has been evaluated """
        if verbosity <= 0:
            return

        if node.expr_name not in ('', 'ws', None):
            print("Evaluated {}, '{}'".format(node.expr_name, node.text))
            print("output={}".format(self.output))
            if verbosity > 1:
                print('state={}'.format(self.processing_state))

    def score(self, node, children):
        """
        Gather outputs for all parts
        """
        if len(self.partstates) == 1:
            ## Unnested output
            d = self.partstates[0]
            self.subbeat_starts = d['subbeat_starts']
            for n in d['subbeat_lengths']:
                self.subbeat_lengths.append(n)
        else:
            for _, d in self.partstates.items():
                self.subbeat_lengths.append(tuple(d['subbeat_lengths']))
                self.subbeat_starts.append(d['subbeat_starts'])

    def partswitch(self, node, children):
        """ Switch to new part """
        newpartnumber = int(node.children[1].text)
        newpindex = newpartnumber - 1
        try:
            self.processing_state = self.partstates[newpindex]
        except KeyError:
            ## Doesn't exist yet. Create it.
            pstate = self.new_part_state()
            self.partstates[newpindex] = pstate
            self.processing_state = self.partstates[newpindex]
            self.current_part = newpindex
            self.beat_map[newpartnumber] = []

    def new_part_state(self):
        """ Returns a new part state dict """
        return dict(
            basetempo=self.first_tempo,
            tempo=self.first_tempo,
            beat_index=0,
            bar_beat_count=0,
            in_chord=False,
            chord_tone_count=0,
            subbeats=0,
            beatspec="4",
            timesig=('M', 0.0, 4, 4),
            subbeat_lengths=[],
            subbeat_starts=[],
            )

    def tempo(self, node, children):
        """ Install a new tempo """
        if self.current_part == 0:
            state = self.processing_state
            newtempo = int(round(float(node.children[1].text)))
            assert newtempo != 0
            state['basetempo'] = state['tempo'] = newtempo
            self.insert_tempo_meta(state)
        else:
            print(
                "Ignoring tempo spec in part {}.".format(self.current_part))

    def key(self, node, children):
        """ Insert a key signature """
        state = self.processing_state
        keyname = node.children[1].text.strip()
        index = state['beat_index']
        sig = keysigs.MIDISIGS[keyname]
        self.meta_output.append(('K', index, sig))

    def relativetempo(self, node, children):
        """ Adjust the current tempo without altering the base tempo """
        if self.current_part == 0:
            state = self.processing_state
            xtempo = float(node.children[1].text)
            assert xtempo != 0.0
            state['tempo'] = int(round(xtempo * state['basetempo']))
            self.insert_tempo_meta(state)
        else:
            print(
                "Ignoring tempo spec in part {}.".format(self.current_part))

    def beatspec(self, node, children):
        """
        Store the new beat division
        """
        state = self.processing_state
        oldbeatspec = state['beatspec']
        newbeatspec = node.children[1].text
        if oldbeatspec != newbeatspec:
            state['beatspec'] = newbeatspec

    def subbeat(self, node, children):
        """
        Add 1 to subbeat count of current beat.
        """
        state = self.processing_state
        state['subbeats'] += 1

    def beat(self, node, children):
        """
        Compute subbeat duration for current beat in current tempo.
        DESIGN NOTE: tbon will not support changing the tempo within
        a beat.
        """
        state = self.processing_state
        mult, numer = TIMESIG_LUT[state['beatspec']]
        #beat_length = 1
        beat_length = 4 * mult / numer
        subbeat_length = beat_length/state['subbeats']

        subbeats = []
        for n in range(state['subbeats']):
            subbeats.append(state['beat_index'] + (n * subbeat_length))
        #self.subbeat_starts.append(tuple(subbeats))
        state['subbeat_starts'].append(tuple(subbeats))
        state['subbeats'] = 0
        state['beat_index'] += beat_length
        state['bar_beat_count'] += 1
        ## if no tempo meta at end of first beat, insert the default.
        if state['beat_index'] == beat_length:
            for m in self.meta_output:
                if m[0] == 'T':
                    break
            else:
                self.insert_tempo_meta(state, index=0)
        state['subbeat_lengths'].append(subbeat_length)
        self.beat_lengths.append(beat_length)

    def barline(self, node, children):
        """ Finish the bar. Add to beat map """
        state = self.processing_state
        partnum = self.current_part + 1
        self.beat_map[partnum].append(state['bar_beat_count'])
        mult, numer = TIMESIG_LUT[state['beatspec']]
        beat_length = 4 * mult / numer
        bar_index = state['beat_index'] - state['bar_beat_count'] * beat_length
        timesig = time_signature(state['beatspec'],
                                 state['bar_beat_count'],
                                 bar_index)
        if bar_index == 0 or state['timesig'][-2:] != timesig[-2:]:
            self.meta_output.append(timesig)
            state['timesig'] = timesig

        state['bar_beat_count'] = 0

    def insert_tempo_meta(self, state, index=None):
        """ Append a tempo meta event """
        if index is None:
            index = state['beat_index']
        self.meta_output.append(('T', index, state['tempo']))




class MidiEvaluator():
    """
    Parses and evaluates a tbon source and produces a time-ordered list of
    tuples representing midi note events in self.output. Each tuple consists of
    (pitch, start, end, velocity, channel) where
      * pitch = midi pitch number
      * start = start time in quarter-note beats
      * end = end time in quarter-note beats
      * velocity = velocity as a number between 0.0 and 1.0,
      * channel = MIDI channel number 1 through 16 inclusive.

    Times are offsets from beginning of the music. Converting the list to
    actual Midi NoteOn and NoteOff events and playing playing them is left up
    to other software.

    The constructor's "ignore_velocity" argument suppresses the inclusion of
    both velocity and channel number. Its primary purpose is to simplify the
    creation of test cases where those items are not needed.

    The self.output list is actually a list of tuples of tuples. The extra
    level is needed to handle compositions in multiple voices, so the actual
    format is
    [ ((p,s,e,v,c), ...), ((p,s,e,v,c), ...)),  ... ]

    The top-level tuples are ordered by part number.

    Other outputs:
    self.meta_output holds Tempo, Key and Time Signature events.

      Tempo: Tuplets of the form ('T', start, bpm) where
             start = start time of new tempo in quarter-note beats
             bpm   = new quarter-note tempo in beats per minute

      Key: Tuplets of the form ('K', start, (sf, mode))
             start = start time of new tempo in quarter-note beats
             sf = Number of sharps (sf > 0) or flats (sf < 0)
             mode = 0 if major, 1 if minor

      Time Signature: Tuplets of the form ('M', start, numerator, denominator)
             start = start time of new tempo in quarter-note beats
             numerator = denominator notes per measure
             denominator = one of [2, 4, 8, 16]

    self.metronome_output. Tuples of metronome clicks in part 1, one per beat.
        * same format as note events (p,s,e,v,c).
        * channel is always 10,
        * velocity follows the music
        * downbeat pitch is high wood block (76)
        * other beats are low wood block (77)

    self.beat_map: List of number of beats in each measure
    """
    def __init__(self,
                 pitch_order=tuple('cdefgab'),
                 ignore_velocity=False):
        self.first_tempo = 120
        self.pitch_order = pitch_order
        self.ignore_velocity = ignore_velocity
        self.pitch_midinumber = dict(zip(pitch_order, (0, 2, 4, 5, 7, 9, 11)))
        self.output = []
        self.metronome_output = []
        self.meta_output = []
        self.beat_map = ()
        self.subbeat_starts = []
        self.subbeat_lengths = None
        self.beat_lengths = []
        self.partstates = {}
        self.processing_state = None
        self.current_part = None

    def new_part_state(self, newpartnumber):
        """ Returns a new part state dict """
        return dict(
            notes=[],
            basetempo=self.first_tempo,
            tempo=self.first_tempo,
            beat_index=0,
            subbeats=0,
            bar_beat_index=0,
            bar_subbeats=0,
            octave=5, ## middle C, midi number 60
            alteration=0,
            pitchname=self.pitch_order[0],
            bar_accidentals={},
            in_chord=NOTE,
            chord_tone_count=0,
            prior_chord_tone_count=0,
            prior_chord_next_index=0,
            keyname="C",
            velocity=0.8,
            de_emphasis=1.0,
            channel=1,
            output=[],
            )

    def eval(self, source, verbosity=2):
        """Evaluate tbon source"""
        ## Preprocess once only.
        if self.subbeat_lengths is None:
            mp = MidiPreEvaluator()
            mp.eval(source, verbosity=0)
            self.subbeat_lengths = mp.subbeat_lengths
            self.subbeat_starts = mp.subbeat_starts
            self.beat_lengths = mp.beat_lengths
            self.meta_output = mp.meta_output
            self.beat_map = {k: tuple(v) for k, v in mp.beat_map.items()}
            ## Update each partstate
            pstates = self.partstates ## shorter name
            for num, state in mp.partstates.items():
                pstates[num] = self.new_part_state(num)
                pstates[num]['subbeat_starts'] = state['subbeat_starts']
                pstates[num]['subbeat_lengths'] = state['subbeat_lengths']
            self.processing_state = pstates[0]
            self.current_part = 0
            #print("PreEval {}".format(mp.output))

        node = parse(source) if isinstance(source, str) else source
        method = getattr(self, node.expr_name, lambda node, children: children)
        ## Recursively evaluate subtree
        method(node, [self.eval(n, verbosity) for n in node])
        self.show_progress(node, verbosity)
        return self.output

    def show_progress(self, node, verbosity):
        """ Call this in self.eval() *after* the node has been evaluated """
        if verbosity <= 0:
            return
        if node.expr_name not in ('', 'ws', None):
            print("Evaluated {}, '{}'".format(node.expr_name, node.text))
            print("output={}".format(self.output))
            print("subbeat_lengths={}".format(self.subbeat_lengths))
            if verbosity > 1:
                print('state={}'.format(self.processing_state))

    def score(self, node, children):
        """
        Add the last note or chord to the list,
        Then convert output list items to tuples.
        If we're ignoring velocity (and channel), the tuples are:
            (pitch, start, end)
        otherwise
            (pitch, start, end, velocity, channel)

        Finally, gather outputs for all parts.
        """
        for _, state in self.partstates.items():
            ## Add the last note or chord to the list,
            for note in state['notes']:
                state['output'].append(note)

            ## sort output by start time
            state['output'] = sorted(state['output'], key=lambda x: x[1])

            ## Convert the music output
            converted = []
            for item in state['output']:
                pitch = item[0]
                start = item[1]
                end = item[2]
                velocity = item[3]
                channel = item[4]
                if self.ignore_velocity:
                    converted.append((pitch, start, end))
                else:
                    converted.append((pitch, start, end,
                                      velocity, channel))

            state['output'] = converted

        ## Convert the metronome output
        converted = []

        for item in self.metronome_output:
            pitch = item[0]
            start = item[1]
            end = item[2]
            velocity = item[3]
            channel = 10 # MIDI Percussion channel
            if self.ignore_velocity:
                converted.append((pitch, start, end))
            else:
                converted.append((pitch, start, end, velocity, channel))

        self.metronome_output = converted

        ## Gather outputs from all parts
        for _, d in self.partstates.items():
            self.output.append(tuple(d['output']))

    def partswitch(self, node, children):
        """ Switch to new part """
        newpartnumber = int(node.children[1].text)
        newpindex = newpartnumber - 1
        try:
            self.processing_state = self.partstates[newpindex]
        except KeyError:
            ## Doesn't exist yet. Create it.
            pstate = self.new_part_state(newpindex)
            self.partstates[newpindex] = pstate
            self.processing_state = self.partstates[newpindex]
        self.current_part = newpindex

    def tempo(self, node, children):
        """ Install a new tempo """
        if self.current_part == 0:
            state = self.processing_state
            newtempo = float(node.children[1].text)
            assert newtempo != 0.0
            state['basetempo'] = state['tempo'] = newtempo
        else:
            print(
                "Ignoring tempo spec in part {}.".format(self.current_part))

    def relativetempo(self, node, children):
        """ Adjust the current tempo without altering the base tempo """
        if self.current_part == 0:
            state = self.processing_state
            newtempo = float(node.children[1].text)
            assert newtempo != 0.0
            state['tempo'] = newtempo * state['basetempo']
        else:
            print(
                "Ignoring tempo spec in part {}.".format(self.current_part))

    def velocity(self, node, children):
        """ Change the current velocity """
        state = self.processing_state
        newvelocity = float(node.children[1].text)
        assert 0.0 <= newvelocity <= 1.0
        state['velocity'] = newvelocity

    def channel(self, node, children):
        """ Change the current channel """
        state = self.processing_state
        newchannel = int(node.children[1].text)
        assert 1 <= newchannel <= 16
        state['channel'] = newchannel

    def de_emphasis(self, node, children):
        """ Change the current de_emphasis """
        state = self.processing_state
        newde_emphasis = float(node.children[1].text)
        assert 0.0 <= newde_emphasis <= 1.0
        state['de_emphasis'] = 1.0 - newde_emphasis

    def bar(self, node, children):
        """ Clear any accidentals """
        self.clear_bar_accidentals()
        state = self.processing_state
        state['bar_beat_index'] = 0
        state['bar_subbeats'] = 0

    def beat(self, node, children):
        """ Update the beat indices and add to metronome_output"""
        state = self.processing_state

        ## Metronome
        velocity = state['velocity']
        channel = 10
        if state['bar_beat_index'] == 0:
            pitchnumber = 76
        else:
            pitchnumber = 77
            velocity *= state['de_emphasis']
        bindex = state['beat_index']
        start = state['subbeat_starts'][bindex][0]
        end = start + self.beat_lengths[bindex]
        self.metronome_output.append([pitchnumber, start, end,
                                      velocity, channel])

        ## Update indices
        state['subbeats'] = 0
        state['beat_index'] += 1
        state['bar_beat_index'] += 1

    def chordstart(self, node, children):
        """
        Close any pending accumulations
        Initialize the state machine for chord tone counting.
        """

        state = self.processing_state
        if state['prior_chord_tone_count'] == 0:
            for note in state['notes']:
                if len(note) > 1:
                    state['output'].append(note)

            state['notes'] = []

        state['in_chord'] = CHORD
        state['prior_chord_next_index'] = 0

    def rollstart(self, node, children):
        """
        Close any pending accumulations
        Initialize the state machine for chord (roll) tone counting.
        """
        state = self.processing_state
        for note in state['notes']:
            if len(note) > 1:
                state['output'].append(note)

        state['notes'] = []

        state['in_chord'] = ROLL
        state['chord_tone_count'] = 0

    def ornamentstart(self, node, children):
        """
        Init an ornament
        Close any pending accumulations
        Initialize the state machine for chord tone counting.
        """
        state = self.processing_state
        for note in state['notes']:
            if len(note) > 1:
                state['output'].append(note)

        state['notes'] = []

        state['in_chord'] = ORNAMENT
        state['chord_tone_count'] = 0

    def rparen(self, node, children):
        """
        Finalize chord, roll, or ornament.
        """
        state = self.processing_state
        if state['in_chord'] == ROLL:
            ## Adjust starts and durations
            ## Before adjustments all durations are equal
            ## to the full subbeat duration.
            count = state['chord_tone_count']
            index = state['beat_index']
            subduration = state['subbeat_lengths'][index]
            subsub_duration = subduration/count
            offset = 0
            for i in range(1, count):
                offset += subsub_duration
                #print("i={},Adjusted duration = {}".format(i, duration))
                state['notes'][i][1] += offset

            state['subbeats'] += 1
            state['bar_subbeats'] += 1

        if state['in_chord'] == ORNAMENT:
            ## Adjust starts and durations
            ## Before adjustments all durations are equal
            ## to the full subbeat duration.
            count = state['chord_tone_count']
            index = state['beat_index']
            subduration = state['subbeat_lengths'][index]
            subsub_duration = subduration/count
            offset = 0
            for i in range(count):
                state['notes'][i][1] += offset
                state['notes'][i][2] = state['notes'][i][1] + subsub_duration
                offset += subsub_duration
            ## Ornament tones (other than the last) do not sustain,
            ## so flush all but the last to the output list
            for i in range(-count, -1):
                state['output'].append(state['notes'][i])
            ## Keep on the last in the extendable note list
            state['notes'] = [state['notes'][-1]]

            state['subbeats'] += 1
            state['bar_subbeats'] += 1
            state['chord_tone_count'] = 1

        elif state['in_chord'] == CHORD:
            ## push leftovers to output
            nnotes = len(state['notes'])
            nleftover = nnotes - state['chord_tone_count']
            while nleftover > 0:
                self.note2output(-nleftover, state)
                nleftover -= 1

            state['subbeats'] += 1
            state['bar_subbeats'] += 1

        state['in_chord'] = NOTE
        state['prior_chord_tone_count'] = state['chord_tone_count']
        state['chord_tone_count'] = 0


    def octave_up(self, node, children):
        """
        Octave up adds 1 to the octave shift count for next pitch.
        """
        state = self.processing_state
        state['octave'] += 1

    def octave_down(self, node, children):
        """
        Octave down subtracts 1 from the octave shift count for next pitch.
        """
        state = self.processing_state
        state['octave'] -= 1

    def doublesharp(self, node, children):
        """ Adds 1 to current pitch alteration count """
        state = self.processing_state
        state['alteration'] += 2

    def sharp(self, node, children):
        """ Adds 1 to current pitch alteration count """
        state = self.processing_state
        state['alteration'] += 1

    def doubleflat(self, node, children):
        """ Subtracts 1 from  current pitch alteration count """
        state = self.processing_state
        state['alteration'] -= 2

    def flat(self, node, children):
        """ Subtracts 1 from  current pitch alteration count """
        state = self.processing_state
        state['alteration'] -= 1

    def natural(self, node, children):
        """
        Sets alteration count to None (not 0) so other code will
        know to cancel any prior accidentals in the bar for next pitch.
        """
        state = self.processing_state
        state['alteration'] = None


    def rest(self, node, children):
        """  rest = "z"
        Encountering a rest triggers the following actions:
          * Close the preceding notes
          * Open a new one
          * Insert None as the midi pitch
        """
        state = self.processing_state
        index = state['beat_index']
        duration = state['subbeat_lengths'][index]
        start = state['subbeat_starts'][index][state['subbeats']]
        if not state['in_chord']:
            for note in state['notes']:
                if len(note) > 1:
                    note[2] = start ## which is the end :-)
                    state['output'].append(note)

        end = start + duration
        if not state['in_chord']:
            state['notes'] = []
            state['subbeats'] += 1
            state['bar_subbeats'] += 1
            state['chord_tone_count'] = 0
            state['prior_chord_tone_count'] = 0
        state['notes'].append([None, start, end,
                               state['velocity'],
                               state['channel'],
                              ])

    def pitchname(self, node, children):
        """  pitchname = ~"[a-g]"i
        Encountering a pitchname triggers the following actions:
          * Close the preceding note
          * Open a new one
          * Look up the midi pitch
            * Adjust relative to prior pitch
          * Apply octave and alterations
          * Insert new midi pitch into current note (the new one)
          * Empty the current alteration and octave accumulators
        TODO Relative pitch needs work.
        """
        state = self.processing_state
        pitchname = node.text.strip()
        state['octave'] += self.octave_change(state['pitchname'], pitchname)

        if state['alteration'] != 0:
            ## Check for None which indicatas a natural sign.
            if state['alteration'] is None:
                state['alteration'] = 0
            ## Update the bar accidentals dict
            self.set_bar_accidental(pitchname,
                                    state['octave'],
                                    state['alteration'])
        alteration = self.get_bar_accidental(pitchname, state['octave'])
        ## For numeric pitchnames the 'alteration' above includes an
        ## offset that maps 1 to the tonic of the current key.

        pitchnumber = self.pitch_midinumber[pitchname]
        pitchnumber += alteration + 12 * state['octave']
        ## De-emphasize offbeats according to current de_emphasis value
        if self.is_downbeat(state):
            velocity = state['velocity'] ## downbeat gets full velocity
        else:
            velocity = state['velocity'] * state['de_emphasis']

        state['alteration'] = 0
        state['pitchname'] = pitchname
        channel = state['channel']
        state['pending_note'] = (pitchnumber,
                                 velocity, channel)

    def pitch(self, node, children):
        """
        Deal with non-chord tones.
        """
        state = self.processing_state
        index = state['beat_index']
        duration = state['subbeat_lengths'][index]
        #start = state['subbeat_starts'][part][index][state['subbeats']]
        start = state['subbeat_starts'][index][state['subbeats']]
        if not state['in_chord']:
            for note in state['notes']:
                if len(note) > 1:
                    note[2] = start ## which is the end :-)
                    state['output'].append(note)

        end = start + duration
        pitchnumber, velocity, channel = state['pending_note']
        if not state['in_chord']:
            state['notes'] = []
            state['subbeats'] += 1
            state['bar_subbeats'] += 1
            state['notes'].append([pitchnumber, start, end,
                                   velocity, channel])
            state['chord_tone_count'] = 0
            state['prior_chord_tone_count'] = 1
        elif state['in_chord'] in (ROLL, ORNAMENT):
            ## Rolls and Ornaments
            state['notes'].append([pitchnumber, start, end,
                                   velocity, channel])
            state['chord_tone_count'] += 1

    def chordpitch(self, node, children):
        """ Deal with chord tones """
        state = self.processing_state
        index = state['beat_index']
        duration = state['subbeat_lengths'][index]
        pitchnumber, velocity, channel = state['pending_note']
        start = state['subbeat_starts'][index][state['subbeats']]
        end = start + duration
        newnote = [pitchnumber, start, end,
                   velocity, channel]
        pchindex = state['prior_chord_next_index']
        try:
            ## Replace if possible, left to right
            state['output'].append(state['notes'][pchindex])
            state['notes'][pchindex] = newnote
            state['prior_chord_next_index'] += 1
        except IndexError:
            ## All prior chord notes already replaced
            state['notes'].append(newnote)
            state['prior_chord_next_index'] += 1
        state['chord_tone_count'] += 1

    def chordhold(self, node, children):
        """ Extend corresponding pitch in prior chord """
        state = self.processing_state
        index = state['beat_index']
        duration = state['subbeat_lengths'][index]
        newend = state['subbeat_starts'][index][state['subbeats']] + duration
        if state['in_chord'] in (CHORD,):
            index = state['prior_chord_next_index']
            state['notes'][index][2] = newend
            state['prior_chord_next_index'] += 1
            state['prior_chord_tone_count'] -= 1
            state['chord_tone_count'] += 1

    def hold(self, node, children):
        """
        A hold triggers the following actions:
          * Add 1 sub-beat to current note duration
          * Add 1 to sub-beat count in current beat.
        """
        state = self.processing_state
        index = state['beat_index']
        duration = state['subbeat_lengths'][index]
        newend = state['subbeat_starts'][index][state['subbeats']] + duration
        if state['in_chord'] in (CHORD,):
            index = state['chord_tone_count']
            state['notes'][index][2] = newend
            state['chord_tone_count'] += 1
        else:
            for note in state['notes']:
                note[2] = newend
            state['subbeats'] += 1
            state['bar_subbeats'] += 1

    def chordrest(self, node, children):
        """
        Drop a note from the notes list and append it to
        the output, replacing it with a rest.
        """
        state = self.processing_state
        index = state['beat_index']
        duration = state['subbeat_lengths'][index]
        pitchnumber, velocity, channel = (None,
                                          state['velocity'],
                                          state['channel'])
        start = state['subbeat_starts'][index][state['subbeats']]
        end = start + duration
        newnote = [pitchnumber, start, end,
                   velocity, channel]
        pchindex = state['prior_chord_next_index']
        try:
            ## Replace if possible, left to right
            state['output'].append(state['notes'][pchindex])
            state['notes'][pchindex] = newnote
            state['prior_chord_next_index'] += 1
            print("Replaced with rest.")
            state['chord_tone_count'] += 1
        except IndexError:
            msg = "Not enough notes in prior chord."
            print(msg)
            raise

    def pitchname_interval_ascending(self, pname0, pname1):
        """
        Returns the musical interval number between the pitchnames assuming the
        second pitch is the nearest higher from the first.
        """
        order = self.pitch_order
        return 1 + (order.index(pname1) - order.index(pname0)) % len(order)

    def octave_change(self, pname0, pname1):
        """
        Return -1, 0, or 1 depending on whether closest instance of pname1 is
        above, within, or below the octave containing pname0.
        """
        interval = self.pitchname_interval_ascending(pname0, pname1)
        if interval == 1: ## Unison
            return 0
        higher = interval < 5
        lower = not higher
        order = self.pitch_order
        index0 = order.index(pname0)
        index1 = order.index(pname1)

        if higher and index1 > index0:
            result = 0
        elif higher and index1 < index0:
            result = 1
        elif lower and index1 > index0:
            result = -1
        else:
            result = 0

        return result

    def keyname(self, node, children):
        """ Install new keyname """
        kn = node.text.strip()
        assert kn in keysigs.KEYSIGS.keys()
        self.processing_state['keyname'] = kn

    def set_bar_accidental(self, pitchname, octave, value):
        """
        Used to support persistent accidentals for the duration of a bar.
        Values are stored in a dictionary keyed by (pitchname, octave).
        """
        _ = self.processing_state['bar_accidentals']
        _[(pitchname, octave)] = value


    def get_bar_accidental(self, pitchname, octave):
        """
        Return the corresponding value or 0.
        """
        _ = self.processing_state['bar_accidentals']
        try:
            bar_accidental = _[(pitchname, octave)]
        except KeyError:
            ## not among bar accidentals
            bar_accidental = None

        ## Apply alterations according to
        ## current key.
        key = self.processing_state['keyname']
        return keysigs.get_alteration(pitchname, key, bar_accidental)

    def clear_bar_accidentals(self):
        """
        Called at end of bar empty the dictionary.
        """
        self.processing_state['bar_accidentals'] = {}

    def is_downbeat(self, state):
        """ Return True or False """
        if state['bar_beat_index'] != 0:
            result = False
        elif state['in_chord'] in (CHORD,):
            ## All notes of chords on downbeat are emphasized
            result = True
        elif state['in_chord'] in (ROLL, ORNAMENT):
            ## but only the first note of rolls and ornaments on downbeat
            result = (state['chord_tone_count'] == 0)
        else:
            ## ordinary subbeats of beat 0 are not emphasized.
            result = (state['bar_subbeats'] == 0)
        return result

    def note2output(self, index, state, replacement=None):
        """
        Append the note at index to output list and remove it from the notes
        list. Return the number of notes moved (1 or 0)
        """
        try:
            state['output'].append(state['notes'].pop(index))
            if replacement is not None:
                state['notes'].insert(index, replacement)
            return 1
        except IndexError:
            return 0
