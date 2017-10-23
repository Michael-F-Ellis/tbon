"""
To be run with pytest
"""
import keysigs
from parser import MidiEvaluator, MidiPreEvaluator
from pytest import approx
#pylint: disable=missing-docstring, invalid-name, singleton-comparison


def test_pre_evaluation():
    mp = MidiPreEvaluator()
    mp.eval('#d - - - |')
    assert mp.output == [1.0] * 4
    mp = MidiPreEvaluator()
    mp.eval('#d - ef z |')
    assert mp.output == [1.0, 1.0, 0.5, 1.0]

def test_chord_pre_evaluation():
    mp = MidiPreEvaluator()
    mp.eval('(ac) - - - |')
    assert mp.output == [1.0] * 4
    mp = MidiPreEvaluator()
    mp.eval('c (ac) - -  |')
    assert mp.output == [1.0] * 4

def test_tempo_change():
    mp = MidiPreEvaluator()
    mp.eval('#d - T=60 ef z |')
    assert mp.output == [1.0, 1.0, 0.5, 1.0]
    assert mp.meta_output == [('T', 0, 120), ('T', 2, 60)]
    evaluate('T=120 #d - | T=60 - - |', [(3, 0.0, 4.0)])

def test_relative_tempo_change():
    mp = MidiPreEvaluator()
    mp.eval('#d - t=0.5 ef z |')
    assert mp.output == [1.0, 1.0, 0.5, 1.0]
    assert mp.meta_output == [('T', 0, 120), ('T', 2, 60)]
    evaluate('T=120 #d - | t=0.5  - - |', [(3, 0.0, 4.0)])

def test_keysig_insert():
    mp = MidiPreEvaluator()
    mp.eval('K=D #d - t=0.5 ef z |')
    assert mp.output == [1.0, 1.0, 0.5, 1.0]
    assert mp.meta_output == [('K', 0, (2, 0)), ('T', 0, 120), ('T', 2, 60)]

def test_melody():
    """
    Evaluating a melody returns a list of tuples representing note events.
    Each tuple contains three numbers:
      * midi pitch number
      * start time in seconds relative to beginning of melody.
      * end time in seconds relative to beginning of melody
    """
    ## Held pitch with sharp
    evaluate('#d - - - |', [(3, 0.0, 4.0)])
    ## Same across a bar line
    evaluate('#d - | - - |', [(3, 0.0, 4.0)])
    ## Flat, Rest pitch is None
    evaluate('@e - | z - |', [(3, 0.0, 2.0), (None, 2.0, 4.0)])
    ## Underscore is also a rest
    evaluate('@e - | _ - |', [(3, 0.0, 2.0), (None, 2.0, 4.0)])
    ## Divided beat, octave up
    evaluate('#d - | -e - |', [(3, 0.0, 2.5,), (4, 2.5, 4.0)])
    ## Octave up remains for subsequent pitch
    evaluate('#d - | -^e f |',
             [(3, 0.0, 2.5,), (16, 2.5, 3.0), (17, 3.0, 4.0)])
    ## Use relative rule to keep pitches close to prior pitch
    evaluate('#d - | -^e c |',
             [(3, 0.0, 2.5,), (16, 2.5, 3.0), (12, 3.0, 4.0)])
    evaluate('#d - | -b c |',
             [(3, 0.0, 2.5,), (-1, 2.5, 3.0), (0, 3.0, 4.0)])
    evaluate('#d - | -b c |',
             [(63, 0.0, 2.5,), (59, 2.5, 3.0), (60, 3.0, 4.0)],
             octave=5)

def test_chord():
    evaluate('(ab)- c |',
             [(57, 0.0, 1.0), (59, 0.0, 1.0), (60, 1.0, 2.0)],
             octave=5)
    evaluate('c (ab)- c |',
             [(60, 0, 1.0), (57, 1.0, 2.0), (59, 1.0, 2.0), (60, 2.0, 3.0)],
             octave=5)
    evaluate('c (ab)(cd) c |',
             [(60, 0, 1.0), (57, 1.0, 1.50), (59, 1.0, 1.50),
              (60, 1.50, 2.0), (62, 1.50, 2.0), (60, 2.0, 3.0)],
             octave=5)

def test_roll():
    evaluate('(:ab) |',
             [(57, 0.0, 1.0), (59, 0.50, 1.0)],
             octave=5)
    evaluate('(:ab) - |',
             [(57, 0.0, 2.0), (59, 0.50, 2.0)],
             octave=5)
    evaluate('c(:ab) - |',
             [(60, 0.0, 0.50), (57, 0.50, 2.0), (59, 0.75, 2.0)],
             octave=5)
    evaluate('(:abcde) - |',
             [(57, 0.0, 2.0), (59, 0.2, 2.0), (60, 0.4, 2.0),
              (62, 0.6, 2.0), (64, 0.8, 2.0)],
             octave=5)

def test_ornament():
    evaluate('(~ab) |',
             [(57, 0.0, 0.50), (59, 0.50, 1.0)],
             octave=5)
    evaluate('(~ab) - |',
             [(57, 0.0, 0.50), (59, 0.50, 2.0)],
             octave=5)

def test_comment():
    evaluate('/* This is a comment! */', [])
    evaluate('/* This is a comment! */ c | ', [(0, 0.0, 1.0)])
    evaluate('/* This is a comment! */ c | /* and another */', [(0, 0.0, 1.0)])

def test_numbers_as_pitches():
    m = MidiEvaluator(pitch_order=tuple('1234567'), ignore_velocity=True)
    m.eval('#2 - | -^3 1 |')
    assert m.output == [(63, 0.0, 2.50), (76, 2.50, 3.0), (72, 3.0, 4.0)]

def test_transpose():
    m = MidiEvaluator(pitch_order=tuple('1234567'), ignore_velocity=True)
    m.eval('#2 - | -^3 1 |')
    assert m.output == [(63, 0.0, 2.50,), (76, 2.50, 3.0), (72, 3.0, 4.0)]
    up1 = m.transpose_output(1)
    assert up1 == [(64, 0.0, 2.50,), (77, 2.50, 3.0), (73, 3.0, 4.0)]
    dn1 = m.transpose_output(-1)
    assert dn1 == [(62, 0.0, 2.50,), (75, 2.50, 3.0), (71, 3.0, 4.0)]

def test_transpose_with_rests():
    m = MidiEvaluator(pitch_order=tuple('1234567'), ignore_velocity=True)
    m.eval('5 - | z 1 |')
    assert m.output == [(55, 0.0, 2.0), (None, 2.0, 3.0), (60, 3.0, 4.0)]
    up1 = m.transpose_output(1)
    assert up1 == [(56, 0.0, 2.0), (None, 2.0, 3.0), (61, 3.0, 4.0)]

def test_bar_accidentals():
    evaluate('c @d d | d - - |',
             [(0, 0.0, 1.0), (1, 1.0, 2.0), (1, 2.0, 3.0), (2, 3.0, 6.0)])
    evaluate('c @d %d | #d - - |',
             [(0, 0.0, 1.0), (1, 1.0, 2.0), (2, 2.0, 3.0), (3, 3.0, 6.0)])
    evaluate('c @d ##d | #d - - |',
             [(0, 0.0, 1.0), (1, 1.0, 2.0), (4, 2.0, 3.0), (3, 3.0, 6.0)])
    evaluate('c @d ##d | @@d - - |',
             [(0, 0.0, 1.0), (1, 1.0, 2.0), (4, 2.0, 3.0), (0, 3.0, 6.0)])

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
             [(61, 0.0, 1.0), (66, 1.0, 2.0)],
             octave=5)
    evaluate('K=b c f |',
             [(61, 0.0, 1.0), (66, 1.0, 2.0)],
             octave=5)
    evaluate('K=D 7 3 |',
             [(61, 0.0, 1.0), (66, 1.0, 2.0)],
             octave=5,
             numeric=True)
    evaluate('K=b 7 3 | K=B 7 3 |',
             [(57, 0.0, 1.0), (62, 1.0, 2.0), (58, 2.0, 3.0), (63, 3.0, 4.0)],
             octave=5,
             numeric=True)
    evaluate('K=C@ c f |',
             [(59, 0.0, 1.0), (64, 1.0, 2.0)],
             octave=5)
    evaluate('K=c# c f |',
             [(61, 0.0, 1.0), (66, 1.0, 2.0)],
             octave=5)
    evaluate('K=e@ %d d | d d |',
             [(62, 0.0, 1.0), (62, 1.0, 2.0), (61, 2.0, 3.0), (61, 3.0, 4.0)],
             octave=5,
             numeric=False)
    evaluate('K=e@ %7 7 | 7 #4 @7|',
             [(62, 0.0, 1.0), (62, 1.0, 2.0),
              (61, 2.0, 3.0), (57, 3.0, 4.0), (61, 4.0, 5.0)],
             octave=5,
             numeric=True)

def test_velocity():
    evaluate('c d |',
             [(60, 0.0, 1.0, 0.8), (62.0, 1.0, 2.0, 0.8)],
             octave=5,
             ignore_velocity=False)
    evaluate('c V=0.9 d |',
             [(60, 0.0, 1.0, 0.8), (62.0, 1.0, 2.0, 0.9)],
             octave=5,
             ignore_velocity=False)

def evaluate(source, expected, octave=0,
             numeric=False, ignore_velocity=True):
    if numeric:
        pitch_order = tuple('1234567')
    else:
        pitch_order = tuple('cdefgab')

    m = MidiEvaluator(pitch_order=pitch_order,
                      ignore_velocity=ignore_velocity)
    m.set_octave(octave)
    m.eval(source)
    for i, t in enumerate(m.output):
        assert t == approx(expected[i])
