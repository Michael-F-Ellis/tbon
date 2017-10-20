"""
To be run with pytest
"""
from parser import MidiEvaluator, MidiPreEvaluator
from pytest import approx
#pylint: disable=missing-docstring, invalid-name, singleton-comparison


def test_pre_evaluation():
    mp = MidiPreEvaluator()
    mp.eval('#d - - - |')
    assert mp.output == [0.5, 0.5, 0.5, 0.5]
    mp = MidiPreEvaluator()
    mp.eval('#d - ef z |')
    assert mp.output == [0.5, 0.5, 0.25, 0.5]

def test_chord_pre_evaluation():
    mp = MidiPreEvaluator()
    mp.eval('(ac) - - - |')
    assert mp.output == [0.5, 0.5, 0.5, 0.5]
    mp = MidiPreEvaluator()
    mp.eval('c (ac) - -  |')
    assert mp.output == [0.5, 0.5, 0.5, 0.5]

def test_tempo_change():
    mp = MidiPreEvaluator()
    mp.eval('#d - T=60 ef z |')
    assert mp.output == [0.5, 0.5, 0.50, 1.0]
    evaluate('T=120 #d - | T=60 - - |', [(3, 0.0, 3.0)])

def test_relative_tempo_change():
    mp = MidiPreEvaluator()
    mp.eval('#d - t=0.5 ef z |')
    assert mp.output == [0.5, 0.5, 0.50, 1.0]
    evaluate('T=120 #d - | t=0.5  - - |', [(3, 0.0, 3.0)])

def test_melody():
    """
    Evaluating a melody returns a list of tuples representing note events.
    Each tuple contains three numbers:
      * midi pitch number
      * start time in seconds relative to beginning of melody.
      * end time in seconds relative to beginning of melody
    """
    ## Held pitch with sharp
    evaluate('#d - - - |', [(3, 0.0, 2.0)])
    ## Same across a bar line
    evaluate('#d - | - - |', [(3, 0.0, 2.0)])
    ## Flat, Rest pitch is None
    evaluate('@e - | z - |', [(3, 0.0, 1.0), (None, 1.0, 2.0)])
    ## Underscore is also a rest
    evaluate('@e - | _ - |', [(3, 0.0, 1.0), (None, 1.0, 2.0)])
    ## Divided beat, octave up
    evaluate('#d - | -e - |', [(3, 0.0, 1.25,), (4, 1.25, 2.0)])
    ## Octave up remains for subsequent pitch
    evaluate('#d - | -^e f |',
             [(3, 0.0, 1.25,), (16, 1.25, 1.5), (17, 1.5, 2.0)])
    ## Use relative rule to keep pitches close to prior pitch
    evaluate('#d - | -^e c |',
             [(3, 0.0, 1.25,), (16, 1.25, 1.5), (12, 1.5, 2.0)])
    evaluate('#d - | -b c |',
             [(3, 0.0, 1.25,), (-1, 1.25, 1.5), (0, 1.5, 2.0)])
    evaluate('#d - | -b c |',
             [(63, 0.0, 1.25,), (59, 1.25, 1.5), (60, 1.5, 2.0)],
             octave=5)

def test_chord():
    evaluate('(ab)- c |',
             [(57, 0.0, 0.5), (59, 0.0, 0.5), (60, 0.5, 1.0)],
             octave=5)
    evaluate('c (ab)- c |',
             [(60, 0, 0.5), (57, 0.5, 1.0), (59, 0.5, 1.0), (60, 1.0, 1.5)],
             octave=5)
    evaluate('c (ab)(cd) c |',
             [(60, 0, 0.5), (57, 0.5, 0.75), (59, 0.5, 0.75),
              (60, 0.75, 1.0), (62, 0.75, 1.0), (60, 1.0, 1.5)],
             octave=5)

def test_roll():
    evaluate('(:ab) |',
             [(57, 0.0, 0.5), (59, 0.25, 0.5)],
             octave=5)
    evaluate('(:ab) - |',
             [(57, 0.0, 1.0), (59, 0.25, 1.0)],
             octave=5)
    evaluate('c(:ab) - |',
             [(60, 0.0, 0.25), (57, 0.25, 1.0), (59, 0.375, 1.0)],
             octave=5)
    evaluate('(:abcde) - |',
             [(57, 0.0, 1.0), (59, 0.1, 1.0), (60, 0.2, 1.0),
              (62, 0.3, 1.0), (64, 0.4, 1.0)],
             octave=5)

def test_ornament():
    evaluate('(~ab) |',
             [(57, 0.0, 0.25), (59, 0.25, 0.5)],
             octave=5)
    evaluate('(~ab) - |',
             [(57, 0.0, 0.25), (59, 0.25, 1.0)],
             octave=5)

def test_comment():
    evaluate('/* This is a comment! */', [])
    evaluate('/* This is a comment! */ c | ', [(0, 0.0, 0.5)])
    evaluate('/* This is a comment! */ c | /* and another */', [(0, 0.0, 0.5)])

def test_numbers_as_pitches():
    m = MidiEvaluator(pitch_order=tuple('1234567'))
    m.eval('#2 - | -^3 1 |')
    assert m.output == [(63, 0.0, 1.25,), (76, 1.25, 1.5), (72, 1.5, 2.0)]

def test_transpose():
    m = MidiEvaluator(pitch_order=tuple('1234567'))
    m.eval('#2 - | -^3 1 |')
    assert m.output == [(63, 0.0, 1.25,), (76, 1.25, 1.5), (72, 1.5, 2.0)]
    up1 = m.transpose_output(1)
    assert up1 == [(64, 0.0, 1.25,), (77, 1.25, 1.5), (73, 1.5, 2.0)]
    dn1 = m.transpose_output(-1)
    assert dn1 == [(62, 0.0, 1.25,), (75, 1.25, 1.5), (71, 1.5, 2.0)]

def test_transpose_with_rests():
    m = MidiEvaluator(pitch_order=tuple('1234567'))
    m.eval('5 - | z 1 |')
    assert m.output == [(55, 0.0, 1.0), (None, 1.0, 1.5), (60, 1.5, 2.0)]
    up1 = m.transpose_output(1)
    assert up1 == [(56, 0.0, 1.0), (None, 1.0, 1.5), (61, 1.5, 2.0)]

def test_bar_accidentals():
    evaluate('c @d d | d - - |',
             [(0, 0.0, 0.5), (1, 0.5, 1.0), (1, 1.0, 1.5), (2, 1.5, 3.0)])
    evaluate('c @d %d | #d - - |',
             [(0, 0.0, 0.5), (1, 0.5, 1.0), (2, 1.0, 1.5), (3, 1.5, 3.0)])
    evaluate('c @d ##d | #d - - |',
             [(0, 0.0, 0.5), (1, 0.5, 1.0), (4, 1.0, 1.5), (3, 1.5, 3.0)])
    evaluate('c @d ##d | @@d - - |',
             [(0, 0.0, 0.5), (1, 0.5, 1.0), (4, 1.0, 1.5), (0, 1.5, 3.0)])

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

def evaluate(source, expected, octave=0):
    m = MidiEvaluator()
    m.set_octave(octave)
    m.eval(source)
    for i, t in enumerate(m.output):
        assert t == approx(expected[i])
