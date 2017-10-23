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
#######################################################################
import keysigs
from parsimonious.grammar import Grammar

#pylint: disable=anomalous-backslash-in-string
def parse(source):
    """Parse tbon Source"""
    grammar = Grammar(
        """
        melody = (comment / bar)+ ws*
        comment = ws* ~r"/\*.*?\*/"i ws*
        bar = (ws* (meta / beat) ws)+ barline
        meta = key / tempo / relativetempo / velocity
        key = "K=" keyname
        keyname = ~r"[a-gA-G](@|#)?"
        tempo = "T=" floatnum
        relativetempo = "t=" floatnum
        velocity = "V=" floatnum
        floatnum = ~r"\d*\.?\d+"i
        beat = subbeat+
        barline = "|"
        extendable = chord / roll / ornament / pitch / rest
        pitch = octave* alteration? pitchname
        chord = chordstart pitch pitch+ rparen
        chordstart = "("
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
        doublesharp = "##"
        sharp = "#"
        doubleflat = "@@"
        flat = "@"
        natural = "%"
        octave_up = "^"
        octave_down = "/"
        pitchname = ~"[a-g1-7]"i
        ws = ~r"\s*"i
        """
        )
    return grammar['melody'].parse(source)
#pylint: enable=anomalous-backslash-in-string

## Sub-beat tyoe constants
NOTE = 0
CHORD = 1
ENDCHORD = 2
ROLL = 3
ENDROLL = 4
ORNAMENT = 5
ENDORNAMENT = 6


class MidiPreEvaluator():
    """
    Parses and evaluates a tbon source and produces a time-ordered list of
    sub-beat durations for each beat.
    """
    #pylint: disable=dangerous-default-value
    def __init__(self, tempo=120):
        self.output = []
        self.meta_output = []
        self.processing_state = dict(
            basetempo=tempo,
            tempo=tempo,
            beat_index=0,
            in_chord=False,
            chord_tone_count=0,
            subbeats=0,
        )
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

    def tempo(self, node, children):
        """ Install a new tempo """
        state = self.processing_state
        newtempo = int(round(float(node.children[1].text)))
        assert newtempo != 0
        state['basetempo'] = state['tempo'] = newtempo
        self.insert_tempo_meta(state)

    def key(self, node, children):
        """ Insert a key signature """
        state = self.processing_state
        keyname = node.children[1].text.strip()
        index = state['beat_index']
        sig = keysigs.MIDISIGS[keyname]
        self.meta_output.append(('K', index, sig))

    def relativetempo(self, node, children):
        """ Adjust the current tempo without altering the base tempo """
        state = self.processing_state
        xtempo = float(node.children[1].text)
        assert xtempo != 0.0
        state['tempo'] = int(round(xtempo * state['basetempo']))
        self.insert_tempo_meta(state)

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
        beat_length = 1
        subbeat_length = beat_length/state['subbeats']
        state['subbeats'] = 0
        state['beat_index'] += 1
        ## if no tempo meta at end of first beat, insert the default.
        if state['beat_index'] == 1:
            for m in self.meta_output:
                if m[0] == 'T':
                    break
            else:
                self.insert_tempo_meta(state, index=0)
        self.output.append(subbeat_length)

    def insert_tempo_meta(self, state, index=None):
        """ Append a tempo meta event """
        if index is None:
            index = state['beat_index']
        self.meta_output.append(('T', index, state['tempo']))




class MidiEvaluator():
    """
    Parses and evaluates a tbon source and produces a time-ordered list of
    tuples representing midi note events. Each tuple consists of
      * midi pitch number
      * start time in seconds
      * end time in seconds
    Times are offsets from beginning of the melody. Converting the list to
    actual Midi NoteOn and NoteOff events and playing playing them is left up
    to other software.
    """
    def __init__(self, tempo=120,
                 pitch_order=tuple('cdefgab'),
                 ignore_velocity=False):
        self.pitch_order = pitch_order
        self.ignore_velocity = ignore_velocity
        self.pitch_midinumber = dict(zip(pitch_order, (0, 2, 4, 5, 7, 9, 11)))
        self.output = []
        self.meta_output = []
        self.processing_state = dict(
            notes=[],
            tempo=tempo,
            beat_index=0,
            subbeats=0,
            octave=5, ## middle C, midi number 60
            alteration=0,
            pitchname=pitch_order[0],
            bar_accidentals={},
            in_chord=NOTE,
            chord_tone_count=0,
            keyname="C",
            velocity=0.8,
        )
        self.subbeat_lengths = None

    def set_octave(self, midi_octave_number):
        """
        Change the processing state octave. If needed
        """
        assert 0 <= midi_octave_number <= 10
        self.processing_state['octave'] = midi_octave_number

    def eval(self, source, verbosity=2):
        """Evaluate tbon source"""
        ## Preprocess once only.
        if self.subbeat_lengths is None:
            mp = MidiPreEvaluator(tempo=self.processing_state['tempo'])
            mp.eval(source, verbosity=0)
            self.subbeat_lengths = mp.output
            self.meta_output = mp.meta_output
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
            if verbosity > 1:
                print('state={}'.format(self.processing_state))

    def transpose_output(self, semitones):
        """
        Return output transposed by semitones (+/-).
        """
        new_output = []
        for note in self.output:
            pitch, start, stop, velocity = note
            if pitch is not None:
                new_output.append((pitch + semitones, start, stop, velocity))
            else:
                ## Keep rests unchanged (pitch == None)
                new_output.append(note)
        return new_output

    def melody(self, node, children):
        """ melody = bar+ ws*
        Add the last note or chord to the list,
        Then convert list items to (pitch, start, stop) tuples.
        """
        state = self.processing_state
        for note in state['notes']:
            self.output.append(note)
        converted = []
        start = None
        end = None
        in_chord = None
        duration = None
        roll_remaining = None
        def transition(new):
            """ Note/Chord transitions """
            nonlocal start, end, in_chord, duration, roll_remaining
            change = (in_chord, new)
            #print("transition: {}".format(change))
            if change in ((None, NOTE), (None, CHORD),
                          (None, ROLL), (None, ORNAMENT)):
                start = 0
                end = duration
                if change[1] == ROLL:
                    roll_remaining = duration
            elif change in ((CHORD, CHORD), (CHORD, ENDCHORD)):
                pass
            elif change in ((NOTE, ROLL), (ENDCHORD, ROLL),
                            (ENDROLL, ROLL), (ENDORNAMENT, ROLL)):
                ## Beginning of roll. First note contains full duration.
                roll_remaining = duration
                start = end
                end += duration
            elif change in ((ROLL, ROLL), (ROLL, ENDROLL)):
                ## Advance the start time by one sub-subbeat
                #print("start={}, roll_remaining={}, duration={}".format(
                #    start, roll_remaining, duration))
                start += roll_remaining - duration
                roll_remaining = duration
            else:
                ## All other transitions advance sequentially with each new note
                ## starting at the end of the prior note.
                start = end
                end += duration
            in_chord = new


        for item in self.output:
            pitch = item[0]
            duration = item[1]
            transition(item[2])
            velocity = item[3]
            if self.ignore_velocity:
                converted.append((pitch, start, end))
            else:
                converted.append((pitch, start, end, velocity))

        self.output = converted

    def tempo(self, node, children):
        """ Install a new tempo """
        state = self.processing_state
        newtempo = float(node.children[1].text)
        assert newtempo != 0.0
        state['basetempo'] = state['tempo'] = newtempo

    def relativetempo(self, node, children):
        """ Adjust the current tempo without altering the base tempo """
        state = self.processing_state
        newtempo = float(node.children[1].text)
        assert newtempo != 0.0
        state['tempo'] = newtempo * state['basetempo']

    def velocity(self, node, children):
        """ Change the current velocity """
        state = self.processing_state
        newvelocity = float(node.children[1].text)
        assert 0.0 <= newvelocity <= 1.0
        state['velocity'] = newvelocity

    def bar(self, node, children):
        """ Clear any accidentals """
        self.clear_bar_accidentals()

    def beat(self, node, children):
        """ Just update the beat index """
        state = self.processing_state
        state['beat_index'] += 1

    def chordstart(self, node, children):
        """
        Close any pending accumulations
        Initialize the state machine for chord tone counting.
        """

        state = self.processing_state
        for note in state['notes']:
            if len(note) > 1:
                self.output.append(note)

        state['notes'] = []
        state['subbeats'] += 1

        state['in_chord'] = CHORD
        state['chord_tone_count'] = 0

    def rollstart(self, node, children):
        """
        Close any pending accumulations
        Initialize the state machine for chord (roll) tone counting.
        """
        state = self.processing_state
        for note in state['notes']:
            if len(note) > 1:
                self.output.append(note)

        state['notes'] = []
        state['subbeats'] += 1

        state['in_chord'] = ROLL
        state['chord_tone_count'] = 0

    def ornamentstart(self, node, children):
        """ Init an ornament """
        self.paren_start(ORNAMENT)

    def paren_start(self, kind):
        """
        Close any pending accumulations
        Initialize the state machine for chord tone counting.
        `kind` must be one of: CHORD, ROLL, ORNAMENT
        """
        state = self.processing_state
        for note in state['notes']:
            if len(note) > 1:
                self.output.append(note)

        state['notes'] = []
        state['subbeats'] += 1

        state['in_chord'] = kind
        state['chord_tone_count'] = 0

    def pitch(self, node, children):
        """
        Deal with chord tones.
        """
        state = self.processing_state
        if state['in_chord']:
            state['chord_tone_count'] += 1

    def rparen(self, node, children):
        """
        Finalize chord, roll, or ornament.
        """
        state = self.processing_state
        if state['in_chord'] == ROLL:
            #print("Closing roll")
            state['notes'][-1][2] = ENDROLL
            ## Adjust starts and durations
            ## Before adjustments all durations are equal
            ## to the full subbeat duration.
            count = state['chord_tone_count']
            subsub_duration = state['notes'][-1][1]/count
            duration = 0
            for i in range(-1, -count, -1):
                duration += subsub_duration
                #print("i={},Adjusted duration = {}".format(i, duration))
                state['notes'][i][1] = duration

        if state['in_chord'] == ORNAMENT:
            #print("Closing ornament")
            state['notes'][-1][2] = ENDORNAMENT
            ## Adjust starts and durations
            ## Before adjustments all durations are equal
            ## to the full subbeat duration.
            count = state['chord_tone_count']
            subsub_duration = state['notes'][-1][1]/count
            for i in range(-1, -(count + 1), -1):
                duration = subsub_duration
                #print("i={},Adjusted duration = {}".format(i, duration))
                state['notes'][i][1] = duration
            ## Ornament tones (other than the last) do not sustain,
            ## so flush all but the last to the output list
            for i in range(-count, -1):
                self.output.append(state['notes'][i])
            ## Keep on the last in the extendable note list
            state['notes'] = [state['notes'][-1]]

        elif state['in_chord'] == CHORD:
            state['notes'][-1][2] = ENDCHORD

        state['in_chord'] = NOTE
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
        if not state['in_chord']:
            for note in state['notes']:
                if len(note) > 1:
                    self.output.append(note)
        index = state['beat_index']
        duration = self.subbeat_lengths[index]
        if not state['in_chord']:
            state['notes'] = []
            state['subbeats'] += 1
        state['notes'].append([None, duration,
                               state['in_chord'],
                               state['velocity'],
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
        if not state['in_chord']:
            for note in state['notes']:
                if len(note) > 1:
                    self.output.append(note)
        index = state['beat_index']
        duration = self.subbeat_lengths[index]
        if not state['in_chord']:
            state['notes'] = []
            state['subbeats'] += 1
        state['notes'].append([pitchnumber, duration,
                               state['in_chord'], state['velocity']])
        state['alteration'] = 0
        state['pitchname'] = pitchname

    def hold(self, node, children):
        """
        A hold triggers the following actions:
          * Add 1 sub-beat to current note duration
          * Add 1 to sub-beat count in current beat.
        """
        state = self.processing_state
        index = state['beat_index']
        duration = self.subbeat_lengths[index]
        for note in state['notes']:
            note[1] += duration
        state['subbeats'] += 1

    def pitchname_interval_ascending(self, pname0, pname1):
        """
        Returns the musical interval number between the pitchnames assuming the
        second pitch is the nearest higher from the first.
        """
        order = self.pitch_order
        #print(order)
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
        #msg = ('interval {interval}, higher {higher}, lower {lower}, ' +
        #       'index0 {index0}, index1 {index1}')
        #print(msg.format(**locals()))
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
        #print(pitchname, key, bar_accidental)
        return keysigs.get_alteration(pitchname, key, bar_accidental)

    def clear_bar_accidentals(self):
        """
        Called at end of bar empty the dictionary.
        """
        self.processing_state['bar_accidentals'] = {}
