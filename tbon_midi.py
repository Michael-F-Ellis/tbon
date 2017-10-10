# -*- coding: utf-8 -*-
"""
When run as a script, this module creates midi files of
  Happy Birthday in F,
  Twinkle Twinkle in D
  Bernstein's America chorus in C from West Side Story.

You can import it and use the make_midi() function to create midi files from
your own tbon input.

Author: Mike Ellis
Copyright 2017 Ellis & Grant, Inc.
Adapted from example at https://github.com/MarkCWirt/MIDIUtil
"""
from midiutil import MIDIFile
from parser import MidiEvaluator

def make_midi(source, outfile, tempo=120, transpose=0,
              volume=100, track=0, channel=0,
              octave=5, numeric=False):
    """
    Parse and evaluate the source string. Write the output
    to the specified outfile name.

    kwargs:
      tempo -- The beat tempo for the midi file in BPM
      transpose -- Number of semitones to transpose the output.
                   May be positive or negative.
      volume -- MIDI track volume
      track  -- Midi file track number
      channel -- MIDI channel number
      octave  -- Initial MIDI octave number (0 - 10)
      numeric -- tbon notation can be either named pitches (cdefgab) or
                 numbers (1234567) with 1 corresponding to 'c'.
    """

    if numeric:
        pitches = tuple('1234567')
    else:
        pitches = tuple('cdefgab')

    tbon = MidiEvaluator(tempo=60, pitch_order=pitches)
    tbon.set_octave(octave)
    ## Note, tempo = 60 means seconds == beats
    ## and MIDIFile wants input in beats.
    tbon.eval(source, verbosity=0)
    notes = tbon.transpose_output(transpose)

    MyMIDI = MIDIFile(1, adjust_origin=True)  # One track
    MyMIDI.addTempo(track, 0, tempo)

    for pitch, start, stop in notes:
        MyMIDI.addNote(track, channel, pitch, start, stop - start, volume)

    with open(outfile, "wb") as output_file:
        MyMIDI.writeFile(output_file)

if __name__ == '__main__':
    #pylint: disable=invalid-name
    happy = """
    cc | d c f | e - cc |
    d c ^g | f - cc |
    ^c a f | e d ^@bb |
    a f g | f - - |
    """
    make_midi(happy, 'happy.mid')

    twinkle = """
    11 ^55 66 5 | 44 33 22 1 |
    11 ^55 66 5 | 44 33 22 1 |
    ^55 44 33 2 | 55 44 33 2 |
    11 ^55 66 5 | 44 33 22 1 |
    """
    make_midi(twinkle, "twinkle.mid", transpose=2, numeric=True)

    bernstein_america = """
    ^555 111 | 6-4 -1- |
    ^555  111 | 2-7 -5- |
    @777 @333 | 2-@7 -4- |
    @333 @666 | 5-^3 -/1- |
    """
    make_midi(bernstein_america, "bernstein_america.mid", numeric=True)
