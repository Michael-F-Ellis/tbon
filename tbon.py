#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Description: Command line executable.
Author: Mike Ellis
Copyright 2017 Ellis & Grant, Inc.
"""
#pylint: disable=too-many-branches
import os
import argparse
from midiutil import MIDIFile, SHARPS, FLATS, MAJOR, MINOR
from parser import MidiEvaluator
def evaluate(source, numeric=True):
    """ Run the MidiEvaluator and return the output """
    if numeric:
        pitches = tuple('1234567')
    else:
        pitches = tuple('cdefgab')

    tbon = MidiEvaluator(pitch_order=pitches)
    tbon.eval(source, verbosity=0)
    return tbon

def make_midi(tbon, outfile,
              firstbar=0,
              quiet=False,
              metronome=0):
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

    ## MIDIUtil zero indexs, so channel 9 is 10,
    ## the normal channel for percussion
    metronome_channel = 9

    parts = tbon.output
    numparts = len(parts)
    print("Found {} parts".format(numparts))
    metronotes = tbon.metronome_output
    if metronome == 0:
        numTracks = numparts
    elif metronome == 1:
        numTracks = 1
    else:
        numTracks = 1 + numparts
    meta = tbon.meta_output
    beat_map = tbon.beat_map
    MyMIDI = MIDIFile(numTracks, adjust_origin=True,
                      removeDuplicates=False, deinterleave=False)
    #MyMIDI.addTempo(track, 0, tempo)
    track = 0
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

    def add_notes(source, trk):
        """ Add all notes in source to trk on chan. """
        for pitch, start, stop, velocity, chan in source:
            if pitch is not None:
                MyMIDI.addNote(trk, chan-1,
                               pitch, start,
                               stop - start,
                               int(velocity * 127))
    if metronome == 0:
        for track, notes in enumerate(parts):
            add_notes(notes, track)
    elif metronome == 1:
        ## Metronome output only.
        add_notes(metronotes, track)
    else:
        ## Both
        for track, notes in enumerate(parts):
            add_notes(notes, track)
        metrotrack = numparts ## because 0-indexing
        add_notes(metronotes, metrotrack)

    with open(outfile, "wb") as output_file:
        MyMIDI.writeFile(output_file)

    if not quiet:
        for partnum, pmap in beat_map.items():
            print_beat_map(partnum, pmap, first_bar_number=firstbar)

def print_beat_map(partnum, beat_map, first_bar_number=0):
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
    print("Part {} Beat Map: Number of beats in each bar".format(partnum))
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
    _parser.add_argument('-v', '--verbose', action='store_true',
                         help="dump the MidiEvaluator output to stdout")
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
        _metro_outfile = _name + "_metronome_only.mid"
        _both_outfile = _name + "_with_metronome.mid"

        print("Processing {}".format(f))
        with open(f) as infile:
            _source = infile.read()
        if not _args.quiet:
            print(_source)
        _tbon = evaluate(_source, _numeric)
        if _args.verbose:
            print(_tbon.output)

        make_midi(_tbon, _outfile,
                  firstbar=_args.firstbar,
                  quiet=_args.quiet,
                  metronome=0)
        print("Created {}".format(_outfile))
        make_midi(_tbon, _metro_outfile,
                  firstbar=_args.firstbar,
                  quiet=True,
                  metronome=1)
        print("Created {}".format(_metro_outfile))
        make_midi(_tbon, _both_outfile,
                  firstbar=_args.firstbar,
                  quiet=True,
                  metronome=2)
        print("Created {}".format(_both_outfile))
