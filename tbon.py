#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Description: Command line executable.
Author: Mike Ellis
Copyright 2017 Ellis & Grant, Inc.
"""
import os
import argparse
from midiutil import MIDIFile, SHARPS, FLATS, MAJOR, MINOR
from parser import MidiEvaluator

def make_midi(source, outfile, transpose=0,
              track=0, channel=0,
              octave=5, numeric=True,
              firstbar=0,
              quiet=False):
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
    beat_map = tbon.beat_map
    MyMIDI = MIDIFile(1, adjust_origin=True)  # One track
    #MyMIDI.addTempo(track, 0, tempo)

    for m in meta:
        if m[0] == 'T':
            MyMIDI.addTempo(track, m[1], m[2])
        elif m[0] == 'K':
            time = m[1]
            sf, mi = m[2]
            mode = MINOR if mi == 1 else MAJOR
            accidentals = abs(sf)
            acc_type = SHARPS if sf > 0 else FLATS
            #print("Inserting key signature at time {}".format(time))
            #print(accidentals, acc_type, mode)
            MyMIDI.addKeySignature(track, time, accidentals, acc_type, mode)
        elif m[0] == 'M':
            ## Time signature
            time = m[1]
            numerator = m[2]
            denominator = m[3]
            ## midi denominator specified a power of 2
            midi_denom = {2:1, 4:2, 8:3}[denominator]
            ## We want to make the midi metronome match beat duration.
            ## This requires recognizing compound meters
            ## See http://midiutil.readthedocs.io/en/1.1.3/class.html
            ## for discussion of arguments to addTimeSignature()
            ## including clocks_per_tick.
            if denominator == 8 and (numerator % 3 == 0):
                metro_clocks = 36
            elif denominator == 4:
                metro_clocks = 24
            elif denominator == 2:
                metro_clocks = 48

            MyMIDI.addTimeSignature(track, time,
                                    numerator,
                                    denominator=midi_denom,
                                    clocks_per_tick=metro_clocks)

    for pitch, start, stop, velocity in notes:
        if pitch is not None:
            MyMIDI.addNote(track, channel,
                           pitch, start,
                           stop - start,
                           int(velocity * 127))

    with open(outfile, "wb") as output_file:
        MyMIDI.writeFile(output_file)

    if not quiet:
        print_beat_map(beat_map, first_bar_number=firstbar)

def print_beat_map(beat_map, first_bar_number=0):
    """
    Output the beat map in a nice readable display with
    beat counts for 10 bars displayed on each line.
       0: 4 4 4 4 4 4 3 3 4 4
      10: 4 4 ...
    """
    bar_number = 10 * (first_bar_number // 10)
    pad = ' ' * 4
    padcount = first_bar_number % 10
    linelist = []
    endmap = False
    remapped = [pad  for _ in range(padcount)] + list(beat_map)
    linecount = 0
    print("Beat Map: Number of beats in each bar")
    while True:
        label = "{:4d}:".format(bar_number)
        linelist.append(label)
        for i in range(10):
            try:
                nbeats = remapped[10*linecount + i]
                if nbeats == pad:
                    nbstr = nbeats
                else:
                    nbstr = "{:4d}".format(nbeats)
                linelist.append(nbstr)
            except IndexError:
                endmap = True
                linelist.append(pad)
        print(' '.join(linelist))
        linelist = []
        linecount += 1
        bar_number += 10
        if endmap:
            break

if __name__ == '__main__':
    _parser = argparse.ArgumentParser()
    _parser.add_argument('-b', '--firstbar', type=int, default=0,
                         help="The measure number of the first measure."
                         " (Used to align beat map output)")
    _parser.add_argument('-q', '--quiet', action='store_true',
                         help="Don't print the input file and "
                         "bar map to stdout.")
    _parser.add_argument('-x', '--transpose', type=int, default=0,
                         help="Number of semitones to transpose up or down."
                         " The default is 0")
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
        if not _args.quiet:
            print(_source)
        make_midi(_source, _outfile,
                  transpose=_args.transpose,
                  numeric=_numeric,
                  firstbar=_args.firstbar,
                  quiet=_args.quiet)
        print("Created {}".format(_outfile))
