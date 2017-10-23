#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Description: Command line executable.
Author: Mike Ellis
Copyright 2017 Ellis & Grant, Inc.
"""
import os
import argparse
from midiutil import MIDIFile
from parser import MidiEvaluator

def make_midi(source, outfile, transpose=0,
              track=0, channel=0,
              octave=5, numeric=True):
    """
    Parse and evaluate the source string. Write the output
    to the specified outfile name.

    kwargs:
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

    tbon = MidiEvaluator(pitch_order=pitches)
    tbon.set_octave(octave)
    tbon.eval(source, verbosity=0)
    notes = tbon.transpose_output(transpose)
    meta = tbon.meta_output
    MyMIDI = MIDIFile(1, adjust_origin=True)  # One track
    #MyMIDI.addTempo(track, 0, tempo)

    for m in meta:
        if m[0] == 'T':
            MyMIDI.addTempo(track, m[1], m[2])
        elif m[0] == 'K':
            time = m[1]
            sf, minor = m[2]
            accidentals = abs(sf)
            acc_type = int(sf >= 0)
            #print("Inserting key signature at time {}".format(time))
            #print(accidentals, acc_type, minor)
            MyMIDI.addKeySignature(track, time, accidentals, acc_type, minor)

    for pitch, start, stop, velocity in notes:
        if pitch is not None:
            MyMIDI.addNote(track, channel,
                           pitch, start,
                           stop - start,
                           int(velocity * 127))

    with open(outfile, "wb") as output_file:
        MyMIDI.writeFile(output_file)
if __name__ == '__main__':
    _parser = argparse.ArgumentParser()
    _parser.add_argument('-x', '--transpose', type=int, default=0,
                         help="Number of semitones to transpose up or down"
                         "The default is '1234567'.")
    _parser.add_argument("filename", nargs='+',
                         help="one or more files of tbon notation")
    _args = _parser.parse_args()
    for f in _args.filename:
        _name, _ext = os.path.splitext(f)
        if _ext.lower() not in (".tba", ".tbn"):
            raise Exception("File xxtension must be .tba or .tbn")
        else:
            _numeric = _ext.lower() == ".tbn"
        _outfile = _name + ".mid"
        print("Processing {}".format(f))
        with open(f) as infile:
            _source = infile.read()
            print(_source)
        make_midi(_source, _outfile,
                  transpose=_args.transpose,
                  numeric=_numeric)
        print("Created {}".format(_outfile))
