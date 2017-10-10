# -*- coding: utf-8 -*-
"""
Description: Parser/processor for CBon notation language
Author: Mike Ellis
Copyright 2017 Ellis & Grant, Inc.
"""
#######################################################################
## Pylint Overrides
## pylint: disable=no-self-use, unused-argument
## pylint: disable=blacklisted-name
## pylint: disable=too-many-public-methods
#######################################################################

from parsimonious.grammar import Grammar

#pylint: disable=anomalous-backslash-in-string
def parse(source):
    """Parse CBon Source"""
    grammar = Grammar(
        """
        melody = bar+ ws*
        bar = (ws* (meta / beat) ws)+ barline
        meta = tempo / relativetempo
        tempo = "T=" floatnum
        relativetempo = "t=" floatnum
        floatnum = ~r"\d*\.?\d+"i
        beat = subbeat+
        barline = "|"
        extendable = pitch / rest
        pitch = octave* alteration? pitchname
        subbeat = extendable / hold
        rest = "z"
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


class MidiPreEvaluator():
    """
    Parses and evaluates a CBon source and produces a time-ordered list of
    sub-beat durations for each beat.
    """
    #pylint: disable=dangerous-default-value
    def __init__(self, tempo=120):
        self.output = []
        self.processing_state = dict(
            basetempo=tempo,
            tempo=tempo,
            beat_index=0,
            subbeats=0,
        )
    #pylint: enable=dangerous-default-value

    def eval(self, source, verbosity=2):
        """Evaluate CBon source"""
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
        newtempo = float(node.children[1].text)
        assert newtempo != 0.0
        state['basetempo'] = state['tempo'] = newtempo


    def relativetempo(self, node, children):
        """ Adjust the current tempo without altering the base tempo """
        state = self.processing_state
        newtempo = float(node.children[1].text)
        assert newtempo != 0.0
        state['tempo'] = newtempo * state['basetempo']

    def subbeat(self, node, children):
        """
        Add 1 to subbeat count of current beat.
        """
        state = self.processing_state
        state['subbeats'] += 1

    def beat(self, node, children):
        """
        Compute subbeat duration for current beat in current tempo.
        DESIGN NOTE: CBon will not support changing the tempo within
        a beat.
        """
        state = self.processing_state
        beat_length = 60/state['tempo']
        subbeat_length = beat_length/state['subbeats']
        state['subbeats'] = 0
        self.output.append(subbeat_length)



class MidiEvaluator():
    """
    Parses and evaluates a CBon source and produces a time-ordered list of
    tuples representing midi note events. Each tuple consists of
      * midi pitch number
      * start time in seconds
      * end time in seconds
    Times are offsets from beginning of the melody. Converting the list to
    actual Midi NoteOn and NoteOff events and playing playing them is left up
    to other software.
    """
    def __init__(self, tempo=120, pitch_order=tuple('cdefgab')):
        self.pitch_order = pitch_order
        self.pitch_midinumber = dict(zip(pitch_order, (0, 2, 4, 5, 7, 9, 11)))
        self.output = []
        self.processing_state = dict(
            note=[],
            tempo=tempo,
            beat_index=0,
            subbeats=0,
            octave=5, ## middle C, midi number 60
            alteration=0,
            pitchname=pitch_order[0],
            bar_accidentals={},
        )
        self.subbeat_lengths = None

    def set_octave(self, midi_octave_number):
        """
        Change the processing state octave. If needed
        """
        assert 0 <= midi_octave_number <= 10
        self.processing_state['octave'] = midi_octave_number

    def eval(self, source, verbosity=2):
        """Evaluate CBon source"""
        ## Preprocess once only.
        if self.subbeat_lengths is None:
            mp = MidiPreEvaluator(tempo=self.processing_state['tempo'])
            mp.eval(source, verbosity=0)
            self.subbeat_lengths = mp.output
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
            pitch, start, stop = note
            new_output.append((pitch + semitones, start, stop))
        return new_output

    def melody(self, node, children):
        """ melody = bar+ ws*
        Add the last note to the list,
        Then convert list items to (pitch, start, stop) tuples.
        """
        state = self.processing_state
        self.output.append(state['note'])
        converted = []
        t = 0.0
        for item in self.output:
            pitch = item[0]
            duration = item[1]
            start = t
            t += duration
            converted.append((pitch, start, t))
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

    def bar(self, node, children):
        """ Clear any accidentals """
        self.clear_bar_accidentals()

    def beat(self, node, children):
        """ Just update the beat index """
        state = self.processing_state
        state['beat_index'] += 1

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
          * Close the preceding note
          * Open a new one
          * Insert None as the midi pitch
        """
        state = self.processing_state
        if len(state['note']) == 2:
            self.output.append(state['note'])
        index = state['beat_index']
        duration = self.subbeat_lengths[index]
        state['note'] = [None, duration]
        state['subbeats'] += 1

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

        pitchnumber = self.pitch_midinumber[pitchname]
        pitchnumber += alteration + 12 * state['octave']
        if len(state['note']) == 2:
            self.output.append(state['note'])
        index = state['beat_index']
        duration = self.subbeat_lengths[index]
        state['note'] = [pitchnumber, duration]
        state['subbeats'] += 1
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
        state['note'][1] += duration
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
            return _[(pitchname, octave)]
        except KeyError:
            return 0

    def clear_bar_accidentals(self):
        """
        Called at end of bar empty the dictionary.
        """
        self.processing_state['bar_accidentals'] = {}
