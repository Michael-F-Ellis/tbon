"""
To be run with pytest. Contains tests specific to multi-part polyphony.
"""
from parser import (MidiEvaluator, MidiPreEvaluator)
from pytest import approx
#pylint: disable=missing-docstring, invalid-name,
#pylint: disable=len-as-condition, singleton-comparison

def test_partswitch():
    ## Verify default behaviour with part one explicit
    src = 'P=1 (/cegc) |'
    pre_evaluate(src, [1.0])
    pre_evaluate(src, [(0.0,)], target='subbeat_starts')
    evaluate(src,
             [((48, 0, 1), (52, 0, 1), (55, 0, 1), (60, 0, 1)),],)
    src = 'P=1 (/cegc) | P=2 //ce |'
    pre_evaluate(src, [(1.0,), (0.5,)])
    pre_evaluate(src, [(0.0,), ((0.0, 0.5))], target='subbeat_starts')
    src = 'P=1 (/cegc) | P=2 //ce | P=1 (gbdf) | P=2 //gb |'
    pre_evaluate(src, [(1.0, 1.0), (0.5, 0.5)])
    #import pdb;pdb.set_trace()
    evaluate('P=1 c | P=2 //ce |',
             [((60, 0, 1.0),), ((36, 0, 0.5), (40, 0.5, 1.0))],)

def pre_evaluate(source, expected, target='subbeat_lengths'):
    m = MidiPreEvaluator()
    m.eval(source)
    assert len(m.partstates) > 0
    if target == 'subbeat_lengths':
        for i, t in enumerate(m.subbeat_lengths):
            assert t == approx(expected[i])
    elif target == 'subbeat_starts':
        for i, p in enumerate(m.partstates.values()):
            for t in p['subbeat_starts']:
                assert t == approx(expected[i])

def evaluate(source, expected,
             numeric=False, ignore_velocity=True):
    if numeric:
        pitch_order = tuple('1234567')
    else:
        pitch_order = tuple('cdefgab')

    m = MidiEvaluator(pitch_order=pitch_order,
                      ignore_velocity=ignore_velocity)
    m.eval(source)
    for i, part in enumerate(m.output):
        for j, note in enumerate(part):
            assert note == approx(expected[i][j])
