# tbon
Typographic Beat-Oriented Notation for music

Tbon is a musical language I developed for my own use about a decade ago.  It's a quick notation shorthand for writing melodies -- by hand or with a computer keyboard -- that also aims to be 'readable' in the sense that it's possible to play from it by sight.

Over the years I'm made several attempt to write a parser using regexes but never found time to get it working properly. I recently came across Erik Rose's [Parsimonious](https://github.com/erikrose/parsimonious) Python PEG and had a working grammar within a couple of hours. I can't say enough good things about Parsimonious.

This repo is very much *alpha* software. That being said, the parser and evaluator are passing all tests and it's possible to write melodies and convert them to midi files quite easily. Moreover, I don't anticipate making any breaking changes to the language at this point (I've been tinkering with the design for ten years now so it feels pretty much final in terms of basic syntax and capabilities).

Tbon borrows ideas from Lilypond, ABC, and music21's TinyNotation. What makes it different is that it's never necessary to explicity specify a note duration (e.g. 1/2, 1/4) or a meter (e.g. 4/4, 6/8, etc). Beats are groups of notes separated by whitespace.

## Installation
There's no installer at present so you'll need to clone the repo or copy the files.

## Dependencies
* The code was written with Python 3.5. I haven't tested with 2.x. 
* The parser requires Parsimonious (pip install parsimonious).
* The test suite needs to be run with PyTest (pip install pytest).
* To create a midi file, you'll need MIDIUtil (pip install MIDIUtil)

## Quick Start
Run `python tbon_midi.py` from within the repo directory. When run as a script, it creates 3 sample files midi files (Happy Birthday, Twinkle Twinkle, and the chorus from Bernstein's 'America' (West Side Story).  

Then look within `tbon_midi.py` to see how use the `make_midi()` function to process your own scores.

To dive deeper, look at `parser.py` and `test_parser.py`.

## Notation
Here's *Happy Birthday* in F major represented in tbon.

```
    cc | d c f  | e - cc |
         d c ^g | f - cc |
         ^c a f | e d ^@bb |
         a f g  | f - - |
```
    
### Explanation
  * Beats are groups of notes separated by whitespace
  * The meter is determined by the number of beats between barlines ('|')
      * You may freely change meters by putting more or fewer beats within a bar.
      
  * Pitch names are represented by a b c d e f g (alternatively by 1 2 3 4 5 6 7)
  * Accidentals: Sharps,flats and naturals are '#', '@' and '%' respectively.
      - Accidentals persist until the end of the measure (standard music convention)
      
  * Melody direction: Pitches move up or down using the Lilypond relative pitch entry convention.
      * By default, the each note is above or below its predecessor based on which interval is smaller.
          * Thus, `c g` will put the g below the c since the 4th below is smaller than the 5th above.
          * To select the more distant upper pitch, you'd write `c ^g`
          * Similarly you'd write 'c /d' to put choose the d a 7th below the c.
  
  * Note durations: tbon can represent *any* rhythm that can be represented in conventional music notation.
    * Hyphen `-` indicates continuation within and across beats (i.e. a tie).
    * `a b c d`  | --> one beat for each note    
    * `a -b c d` | --> 1.5 beat for the `a` , 0.5 for the `b`, 1 each `c` and `d'.
    * `ab c d -` | --> 0.5 each for `ab`, 1 for `c`, 2 for `d`.
    * `a - b - | - - c -` | --> 2 beats for `a`, 4 for `b`, 2 for `c`
    * `abc c--d e f` | --> triplet `abc`, 0.75 dotted `c`, 0.25 `d`, 1 each `e` and `f`.
    
Here's the chorus of Leonard Bernstein's *America* theme for West Side Story. I've shown it with numerical pitches just to illustrate that tbon supports those. More importantly, notice how easily tbon represents Bernstein's shifts between 6/8 and 3/4 time on alternate bars 


```
    ^555 111  | 6-4 -1- |
    ^555 111  | 2-7 -5- |
    @777 @333 | 2-@7 -4- |
    @333 @666 | 5-^3 -/1- |
```

## Contributing
All suggestions and questions are welcome. I'd especially welcome help putting together a good setup.py to make it easy to put tbon on PyPi. As this is my first serious attempt at writing a parser, I'd also welcome suggestions for improving what I presently have (though it seems to be working rather well at the moment). See the issues section for more ideas.

          
