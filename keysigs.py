# -*- coding: utf-8 -*-
"""
Description: Defines key signatures and provides lookup functions.
Author: Mike Ellis
Copyright 2017 Ellis & Grant, Inc
"""

KEYSIGS = {
    ## 0 = natural, 1 = sharp, -1 = flat
    ## Major keys
    'C': (0, 0, 0, 0, 0, 0, 0),
    'G': (0, 0, 0, 1, 0, 0, 0),
    'D': (1, 0, 0, 1, 0, 0, 0),
    'A': (1, 0, 0, 1, 1, 0, 0),
    'E': (1, 1, 0, 1, 1, 0, 0),
    'B': (1, 1, 0, 1, 1, 1, 0),
    'F#': (1, 1, 1, 1, 1, 1, 0),
    'C#': (1, 1, 1, 1, 1, 1, 1),
    'C@': (-1, -1, -1, -1, -1, -1, -1),
    'G@': (-1, -1, -1, 0, -1, -1, -1),
    'D@': (0, -1, -1, 0, -1, -1, -1),
    'A@': (0, -1, -1, 0, 0, -1, -1),
    'E@': (0, 0, -1, 0, 0, -1, -1),
    'B@': (0, 0, -1, 0, 0, 0, -1),
    'F': (0, 0, 0, 0, 0, 0, -1),
    ## Minor keys
    'a': (0, 0, 0, 0, 0, 0, 0),
    'e': (0, 0, 0, 1, 0, 0, 0),
    'b': (1, 0, 0, 1, 0, 0, 0),
    'f#': (1, 0, 0, 1, 1, 0, 0),
    'c#': (1, 1, 0, 1, 1, 0, 0),
    'g#': (1, 1, 0, 1, 1, 1, 0),
    'd#': (1, 1, 1, 1, 1, 1, 0),
    'a#': (1, 1, 1, 1, 1, 1, 1),
    'a@': (-1, -1, -1, -1, -1, -1, -1),
    'e@': (-1, -1, -1, 0, -1, -1, -1),
    'b@': (0, -1, -1, 0, -1, -1, -1),
    'f': (0, -1, -1, 0, 0, -1, -1),
    'c': (0, 0, -1, 0, 0, -1, -1),
    'g': (0, 0, -1, 0, 0, 0, -1),
    'd': (0, 0, 0, 0, 0, 0, -1),
}

MIDISIGS = {}
# See http://midi.teragonaudio.com/tech/midifile/key.htm
for k, v in KEYSIGS.items():
    sf = sum(v)
    mi = int(k[0] in 'abcdefg')
    MIDISIGS[k] = (sf, mi)

def get_alteration(pitchname, keyname, bar_alteration=None):
    """ Look up the alteration for pitchname in keyname """
    if pitchname in 'cdefgab':
        ## Alpha pitches
        if bar_alteration is None:
            pindex = 'cdefgab'.index(pitchname)
            keysig = KEYSIGS[keyname]
            alteration = keysig[pindex]
        else:
            alteration = bar_alteration
    else:
        ## Numeric pitches
        ## For numeric pitches we return an alteration that
        ## treats 1 as the tonic of the key rather than as an
        ## alias for 'c". For example, if the keyname is D,
        ## then 1 2 4 5 6 as pitchnamea get an alteration of +2
        ## and 3 7, which are sharped get an alteration of +3
        alteration = key_offset_semitones(keyname)
        #print("{}, {}, {}, {}".format(pitchname, keyname,
        #                              alteration, bar_alteration))
        if bar_alteration is None:
            ## Check for minor. keyname will be lower case.
            if keyname[0] in 'abcdefg':
                ## Minor keys get flats on 3, 6, 7
                if '1234567'.index(pitchname) + 1  in  (3, 6, 7):
                    alteration -= 1
        else:
            alteration += bar_alteration

    return alteration

KEYOFFSETS = {
    ## 0 = natural, 1 = sharp, -1 = flat
    ## Major keys
    'C': 0,
    'G': -5,
    'D': 2,
    'A': -3,
    'E': 4,
    'B': -1,
    'F#': 6,
    'C#': 1,
    'C@': -1,
    'G@': -6,
    'D@': 1,
    'A@': -4,
    'E@': 3,
    'B@': -2,
    'F': 5,
    ## Minor keys
    'a': -3,
    'e': 4,
    'b': -1,
    'f#': 6,
    'c#': 1,
    'g#': -4,
    'd#': 3,
    'a#': -2,
    'a@': -4,
    'e@': 3,
    'b@': -2,
    'f': 5,
    'c': 0,
    'g': -5,
    'd':2,
}
def key_offset_semitones(keyname):
    """ TBD """
    return KEYOFFSETS[keyname]
