"""
To be run with pytest
"""
from parser import (MidiEvaluator, MidiPreEvaluator, time_signature)
from pytest import approx
import keysigs
#pylint: disable=missing-docstring, invalid-name, singleton-comparison


def test_pre_evaluation():
    mp = MidiPreEvaluator()
    mp.eval('#d - - - |')
    assert mp.subbeat_lengths == [1.0] * 4
    mp = MidiPreEvaluator()
    mp.eval('#d - ef z |')
    assert mp.subbeat_lengths == [1.0, 1.0, 0.5, 1.0]

def test_subbeat_pre_evaluation():
    mp = MidiPreEvaluator()
    mp.eval('#d - - - |')
    assert mp.subbeat_starts == [(0.0,), (1.0,), (2.0,), (3.0,)]
    mp = MidiPreEvaluator()
    mp.eval('#d - ef z | -g a - (ab) |')
    assert mp.subbeat_starts == [(0.0,), (1.0,), (2.0, 2.5), (3.0,),
                                 (4.0, 4.5), (5.0,), (6.0,), (7.0,)]
    mp = MidiPreEvaluator()
    mp.eval('#d - ef z | B=8  -g a - (ab) |')
    assert mp.subbeat_starts == [(0.0,), (1.0,), (2.0, 2.5), (3.0,),
                                 (4.0, 4.25), (4.5,), (5.0,), (5.5,)]

def test_chord_pre_evaluation():
    mp = MidiPreEvaluator()
    mp.eval('(ac) - - - |')
    assert mp.subbeat_lengths == [1.0] * 4
    mp = MidiPreEvaluator()
    mp.eval('c (ac) - -  |')
    assert mp.subbeat_lengths == [1.0] * 4

def test_tempo_change():
    mp = MidiPreEvaluator()
    mp.eval('#d - T=60 ef z |')
    assert mp.subbeat_lengths == [1.0, 1.0, 0.5, 1.0]
    assert mp.meta_output == [('T', 0, 120), ('T', 2, 60), ('M', 0, 4, 4)]
    evaluate('T=120 #d - | T=60 - - |', [(63, 0.0, 4.0)])

def test_relative_tempo_change():
    mp = MidiPreEvaluator()
    mp.eval('#d - t=0.5 ef z |')
    assert mp.subbeat_lengths == [1.0, 1.0, 0.5, 1.0]
    assert mp.meta_output == [('T', 0, 120), ('T', 2, 60), ('M', 0, 4, 4)]
    evaluate('T=120 #d - | t=0.5  - - |', [(63, 0.0, 4.0)])
    evaluate('#d - | t=0.5  - - |', [(63, 0.0, 4.0)])

def test_keysig_insert():
    mp = MidiPreEvaluator()
    mp.eval('K=D #d - t=0.5 ef z |')
    assert mp.subbeat_lengths == [1.0, 1.0, 0.5, 1.0]
    assert mp.meta_output == [('K', 0, (2, 0)), ('T', 0, 120),
                              ('T', 2, 60), ('M', 0, 4, 4)]

def test_beat_map():
    mp = MidiPreEvaluator()
    mp.eval('a b cd | e f - a |')
    assert mp.beat_map == {1: [3, 4]}
    m = MidiEvaluator(pitch_order=tuple('abcdefg'), ignore_velocity=True)
    m.eval('a b cd | e f - a |')
    assert m.beat_map == {1: (3, 4)}

def test_melody():
    """
    Evaluating a melody returns a list of tuples representing note events.
    Each tuple contains three numbers:
      * midi pitch number
      * start time in seconds relative to beginning of melody.
      * end time in seconds relative to beginning of melody
    """
    ## Held pitch with sharp
    evaluate('#d - - - |', [(63, 0.0, 4.0)])
    ## Same across a bar line
    evaluate('#d - | - - |', [(63, 0.0, 4.0)])
    ## Flat, Rest pitch is None
    evaluate('@e - | z - |', [(63, 0.0, 2.0), (None, 2.0, 4.0)])
    ## Underscore is also a rest
    evaluate('@e - | _ - |', [(63, 0.0, 2.0), (None, 2.0, 4.0)])
    ## Divided beat, octave up
    evaluate('#d - | -e - |', [(63, 0.0, 2.5,), (64, 2.5, 4.0)])
    ## Octave up remains for subsequent pitch
    evaluate('#d - | -^e f |',
             [(63, 0.0, 2.5,), (76, 2.5, 3.0), (77, 3.0, 4.0)])
    ## Use relative rule to keep pitches close to prior pitch
    evaluate('#d - | -^e c |',
             [(63, 0.0, 2.5,), (76, 2.5, 3.0), (72, 3.0, 4.0)])
    evaluate('#d - | -b c |',
             [(63, 0.0, 2.5,), (59, 2.5, 3.0), (60, 3.0, 4.0)])
    evaluate('#d - | -b c |',
             [(63, 0.0, 2.5,), (59, 2.5, 3.0), (60, 3.0, 4.0)],)

def test_barline():
    """ Verify that : and | are equivalent """
    evaluate('#d - | -e - |', [(63, 0.0, 2.5,), (64, 2.5, 4.0)])
    evaluate('#d - : -e - :', [(63, 0.0, 2.5,), (64, 2.5, 4.0)])
    ## Verify roll start (: does not conflict with : as barline
    evaluate('(:ab) :',
             [(57, 0.0, 1.0), (59, 0.50, 1.0)],)

def test_chord():
    evaluate('(ab)- c |',
             [(57, 0.0, 1.0), (59, 0.0, 1.0), (60, 1.0, 2.0)],)
    evaluate('c (ab)- c |',
             [(60, 0, 1.0), (57, 1.0, 2.0), (59, 1.0, 2.0), (60, 2.0, 3.0)],)
    evaluate('c (ab)(cd) c |',
             [(60, 0, 1.0), (57, 1.0, 1.50), (59, 1.0, 1.50),
              (60, 1.50, 2.0), (62, 1.50, 2.0), (60, 2.0, 3.0)],)
    evaluate('(ab)(gcd) |',
             [(57, 0.0, 0.50), (59, 0.0, 0.50),
              (55, 0.50, 1.0), (60, 0.50, 1.0), (62, 0.50, 1.0)],)
    evaluate('c (ab)(gcd) c |',
             [(60, 0, 1.0),
              (57, 1.0, 1.50), (59, 1.0, 1.50),
              (55, 1.50, 2.0), (60, 1.50, 2.0), (62, 1.50, 2.0),
              (60, 2.0, 3.0)],)
    evaluate('c (ab)(gcde) c |',
             [(60, 0, 1.0), (57, 1.0, 1.50), (59, 1.0, 1.50),
              (55, 1.50, 2.0), (60, 1.50, 2.0),
              (62, 1.50, 2.0), (64, 1.50, 2.0),
              (60, 2.0, 3.0)],)
    evaluate('c (ab)(g^de) c |',
             [(60, 0, 1.0), (57, 1.0, 1.50), (59, 1.0, 1.50),
              (55, 1.50, 2.0), (62, 1.50, 2.0), (64, 1.50, 2.0),
              (60, 2.0, 3.0)],)
    evaluate('c (ab)(cde) (/ab) c |',
             [(60, 0, 1.0),
              (57, 1.0, 1.50), (59, 1.0, 1.50),
              (60, 1.50, 2.0), (62, 1.50, 2.0), (64, 1.50, 2.0),
              (57, 2.0, 3.0), (59, 2.0, 3.0),
              (60, 3.0, 4.0)],)

def test_polychord():
    evaluate('a (-c) |', [(57, 0.0, 2.0), (60, 1.0, 2.0)],)
    evaluate('a (-c) (b-) |', [(57, 0.0, 2.0),
                               (60, 1.0, 3.0),
                               (59, 2.0, 3.0)],)
    evaluate('(caa^e) (z/f-z) |', [(60, 0.0, 1.0), (57, 0.0, 1.0),
                                   (64, 0.0, 1.0), (57, 0.0, 2.0),
                                   (None, 1.0, 2.0), (53, 1.0, 2.0),
                                   (None, 1.0, 2.0)],)
    evaluate('(aa) (f-) |', [(57, 0.0, 1.0), (57, 0.0, 2.0),
                             (53, 1.0, 2.0)],)
    evaluate('c (ab)(g-^e) c |',
             [(60, 0, 1.0),
              (57, 1.0, 1.50), (59, 1.0, 2.0),
              (55, 1.50, 2.0), (64, 1.50, 2.0),
              (60, 2.0, 3.0)],)
    evaluate('K=A@ (73) - (-#2) - |', [(60, 0.0, 2.0), (55, 0.0, 4.0),
                                       (59, 2.0, 4.0)],
             numeric=True,)

def test_roll():
    evaluate('(:ab) |',
             [(57, 0.0, 1.0), (59, 0.50, 1.0)],)
    evaluate('(:ab) - |',
             [(57, 0.0, 2.0), (59, 0.50, 2.0)],)
    evaluate('c(:ab) - |',
             [(60, 0.0, 0.50), (57, 0.50, 2.0), (59, 0.75, 2.0)],)
    evaluate('(:abcde) - |',
             [(57, 0.0, 2.0), (59, 0.2, 2.0), (60, 0.4, 2.0),
              (62, 0.6, 2.0), (64, 0.8, 2.0)],)
    evaluate('(:1351) 6 (572) |',
             [(60, 0.0, 1.0), (64, 0.25, 1.0), (67, 0.5, 1.0), (72, 0.75, 1.0),
              (69, 1.0, 2.0),
              (67, 2.0, 3.0), (71, 2.0, 3.0), (74, 2.0, 3.0)],
             numeric=True,)

def test_ornament():
    evaluate('(~ab) |',
             [(57, 0.0, 0.50), (59, 0.50, 1.0)],)
    evaluate('(~ab) - |',
             [(57, 0.0, 0.50), (59, 0.50, 2.0)],)
    evaluate('(~ab)c (ab) |',
             [(57, 0.0, 0.25), (59, 0.25, .50), (60, 0.50, 1.0),
              (57, 1.0, 2.0), (59, 1.0, 2.0)],)
    evaluate('(~^1717) 6 (572) |',
             [(72, 0.0, 0.25), (71, 0.25, 0.5),
              (72, 0.5, 0.75), (71, 0.75, 1.0),
              (69, 1.0, 2.0),
              (67, 2.0, 3.0), (71, 2.0, 3.0), (74, 2.0, 3.0)],
             numeric=True,)

def test_comment():
    evaluate('/* This is a comment! */', [])
    evaluate('/* This is a comment! */ c | ', [(60, 0.0, 1.0)])
    evaluate('P=1 /*  */ B=4 /* */ c /* */ | ', [(60, 0.0, 1.0)])
    evaluate('/* This is a comment! */ c | /* and another */', [(60, 0.0, 1.0)])

def test_numbers_as_pitches():
    evaluate('#2 - | -^3 1 |',
             [(63, 0.0, 2.50), (76, 2.50, 3.0), (72, 3.0, 4.0)],
             numeric=True)

def test_bar_accidentals():
    evaluate('c @d d | d - - |',
             [(60, 0.0, 1.0), (61, 1.0, 2.0), (61, 2.0, 3.0), (62, 3.0, 6.0)])
    evaluate('c @d %d | #d - - |',
             [(60, 0.0, 1.0), (61, 1.0, 2.0), (62, 2.0, 3.0), (63, 3.0, 6.0)])
    evaluate('c @d ##d | #d - - |',
             [(60, 0.0, 1.0), (61, 1.0, 2.0), (64, 2.0, 3.0), (63, 3.0, 6.0)])
    evaluate('c @d ##d | @@d - - |',
             [(60, 0.0, 1.0), (61, 1.0, 2.0), (64, 2.0, 3.0), (60, 3.0, 6.0)])

def test_unicode_accidentals():
    evaluate("c♭c 𝄫c♭c ♮c♯c 𝄪c♯c | c - - - |",
             [(60, 0.0, 0.50), (59, 0.50, 1.0), (58, 1.0, 1.50),
              (59, 1.50, 2.0), (60, 2.0, 2.50), (61, 2.50, 3.0),
              (62, 3.0, 3.50), (61, 3.50, 4.0), (60, 4.0, 8.0)],)

def test_pitchname_interval_ascending():
    m = MidiEvaluator()
    assert m.pitchname_interval_ascending('c', 'c') == 1 # unison
    assert m.pitchname_interval_ascending('b', 'c') == 2 # second
    assert m.pitchname_interval_ascending('d', 'g') == 4 # 4th
    assert m.pitchname_interval_ascending('g', 'd') == 5 # 5th
    assert m.pitchname_interval_ascending('a', 'g') == 7 # 7th

def test_octave_change():
    m = MidiEvaluator()
    assert m.octave_change('c', 'c') == 0
    assert m.octave_change('c', 'b') == -1
    assert m.octave_change('g', 'c') == 1
    assert m.octave_change('g', 'b') == 0
    assert m.octave_change('g', 'd') == 0

def test_midisigs():
    assert keysigs.MIDISIGS['a'] == (0, 1)
    assert keysigs.MIDISIGS['a@'] == (-7, 1)
    assert keysigs.MIDISIGS['A'] == (3, 0)
    assert keysigs.MIDISIGS['A@'] == (-4, 0)

def test_get_key_alteration():
    assert keysigs.get_alteration('c', 'C') == 0
    assert keysigs.get_alteration('c', 'D') == 1
    assert keysigs.get_alteration('c', 'a@') == -1
    assert keysigs.get_alteration('1', 'C') == 0
    assert keysigs.get_alteration('1', 'D') == 2
    assert keysigs.get_alteration('1', 'a@') == -4

def test_key():
    evaluate('K=D c f |',
             [(61, 0.0, 1.0), (66, 1.0, 2.0)],)
    evaluate('K=b c f |',
             [(61, 0.0, 1.0), (66, 1.0, 2.0)],)
    evaluate('K=D 7 3 |',
             [(61, 0.0, 1.0), (66, 1.0, 2.0)],
             numeric=True)
    evaluate('K=b 7 3 | K=B 7 3 |',
             [(57, 0.0, 1.0), (62, 1.0, 2.0), (58, 2.0, 3.0), (63, 3.0, 4.0)],
             numeric=True)
    evaluate('K=C@ c f |',
             [(59, 0.0, 1.0), (64, 1.0, 2.0)],)
    evaluate('K=c# c f |',
             [(61, 0.0, 1.0), (66, 1.0, 2.0)],)
    evaluate('K=e@ %d d | d d |',
             [(62, 0.0, 1.0), (62, 1.0, 2.0), (61, 2.0, 3.0), (61, 3.0, 4.0)],
             numeric=False)
    evaluate('K=e@ %7 7 | 7 #4 @7|',
             [(62, 0.0, 1.0), (62, 1.0, 2.0),
              (61, 2.0, 3.0), (57, 3.0, 4.0), (61, 4.0, 5.0)],
             numeric=True)

def test_velocity():
    evaluate('c d |',
             [(60, 0.0, 1.0, 0.8, 1), (62.0, 1.0, 2.0, 0.8, 1)],
             ignore_velocity=False)
    evaluate('c V=0.9 d |',
             [(60, 0.0, 1.0, 0.8, 1), (62.0, 1.0, 2.0, 0.9, 1)],
             ignore_velocity=False)

def test_de_emphasis():
    evaluate('D=0.125 c d |',
             [(60, 0.0, 1.0, 0.8, 1), (62.0, 1.0, 2.0, 0.7, 1)],
             ignore_velocity=False)
    evaluate('D=0.125 c d | e f |',
             [(60, 0.0, 1.0, 0.8, 1), (62.0, 1.0, 2.0, 0.7, 1),
              (64, 2.0, 3.0, 0.8, 1), (65.0, 3.0, 4.0, 0.7, 1)],
             ignore_velocity=False)
    evaluate('D=0.125 (ce) d |',
             [(60, 0.0, 1.0, 0.8, 1), (64, 0.0, 1.0, 0.8, 1),
              (62.0, 1.0, 2.0, 0.7, 1)],
             ignore_velocity=False)
    evaluate('D=0.125 (:ce) d |',
             [(60, 0.0, 1.0, 0.8, 1), (64, 0.5, 1.0, 0.7, 1),
              (62.0, 1.0, 2.0, 0.7, 1)],
             ignore_velocity=False)
    evaluate('D=0.125 (~ce) d |',
             [(60, 0.0, 0.5, 0.8, 1), (64, 0.5, 1.0, 0.7, 1),
              (62.0, 1.0, 2.0, 0.7, 1)],
             ignore_velocity=False)

def test_beatspec():
    evaluate('B=4 #d - - - |', [(63, 0.0, 4.0)])
    evaluate('B=4. #d - - - |', [(63, 0.0, 6.0)])

def test_time_signature():
    sig = time_signature('4.', 3, 0.0)
    assert sig == ('M', 0.0, 9, 8)

def test_channel():
    evaluate('C=16 c |', [(60, 0.0, 1.0, 0.8, 16)],
             ignore_velocity=False)

def evaluate(source, expected, numeric=False,
             ignore_velocity=True):
    """ Part 0 only """
    if numeric:
        pitch_order = tuple('1234567')
    else:
        pitch_order = tuple('cdefgab')

    m = MidiEvaluator(pitch_order=pitch_order,
                      ignore_velocity=ignore_velocity)
    m.eval(source)
    for i, t in enumerate(m.output[0]):
        assert t == approx(expected[i])

def test_metronome():
    metroevaluate('a b - cd  |', [(76, 0.0, 1.0, 0.8, 10),
                                  (77, 1.0, 2.0, 0.8, 10),
                                  (77, 2.0, 3.0, 0.8, 10),
                                  (77, 3.0, 4.0, 0.8, 10)],
                  ignore_velocity=False)

    metroevaluate('B=4. a b |', [(76, 0.0, 1.5, 0.8, 10),
                                 (77, 1.5, 3.0, 0.8, 10)],
                  ignore_velocity=False)

    metroevaluate('B=4. D=0.25 a b |', [(76, 0.0, 1.5, 0.8, 10),
                                        (77, 1.5, 3.0, 0.6, 10)],
                  ignore_velocity=False)

def metroevaluate(source, expected,
                  numeric=False, ignore_velocity=True):
    if numeric:
        pitch_order = tuple('1234567')
    else:
        pitch_order = tuple('cdefgab')

    m = MidiEvaluator(pitch_order=pitch_order,
                      ignore_velocity=ignore_velocity)
    m.eval(source)
    print(m.metronome_output)
    for i, t in enumerate(m.metronome_output):
        assert t == approx(expected[i])
