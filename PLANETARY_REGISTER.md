# Compositional planetary register

## What changed in 0.32

Version 0.31 made a design mistake: it assigned an indivisible word to each of
22 advanced quantities. Words such as `parlik` “stellar mass” and `luprat`
“mean solar day” merely renamed database columns. They did not show how Losica
could construct a technical meaning from reusable parts.

Version 0.32 retires all 22 forms. A quantity ID still exists in metadata so a
decoded statement can point to one exact source field, but no `quantity:*` ID
has a word. On the surface, each quantity is a prefix expression built from
ordinary atoms and fixed-arity operators. Nineteen atoms reuse existing Losica
words; 37 genuinely missing atoms/operators receive new forms. The same parts
recur across different definitions.

This is a finite scientific register, not a claim that Losica is an
unrestricted natural language. It recovers 22 scalar facts from the pinned
`losica-131757842` physical-climate state. Its archive SHA-256 is
`8cf16f9cb6220dd5759da752c8f719d1561bba97bf63bd56f141716b45c0b0e1`.

## Composition, not labels

For example, the two mass fields share the same construction:

```text
stellar mass  = of(mass, star)
planet mass   = of(mass, planet)
```

The semimajor axis and eccentricity expose their reusable definitions:

```text
semimajor axis = half(longest(of(diameter, of(orbit, planet))))

eccentricity = per(
  half(between(of(focus, of(orbit, planet)),
               of(focus, of(orbit, planet)))),
  half(longest(of(diameter, of(orbit, planet))))
)
```

The written/spoken stream uses prefix order. Each operator declares whether it
takes one or two arguments, so the decoder reconstructs the tree without
parentheses. Source-level molecules such as “planet surface” are macros only;
they expand completely and have no words of their own.

The distinctions are based on reductive semantic paraphrase and published
technical definitions. The seed records links to NSM methodology, the BIPM
Vocabulary of Metrology, JPL orbital definitions, and NASA time and temperature
definitions. These sources constrain the decompositions; they do not establish
that the inventory is a universal semantic minimum.

## Claim grammar

| Part | Required burden |
|---|---|
| `CLAIM` | Opens exactly one typed scalar claim. |
| `EVIDENCE` | Says `sampled`, `derived`, `modeled`, `conditioned`, or `uncertain`. |
| `SUBJECT` | Reuses the same `star` or `planet` atom found inside expressions. |
| `QUANTITY EXPRESSION` | A variable-length prefix tree of reusable atoms and operators. |
| `NUMBER` | Preserves the exact decimal spelling, or an explicit null. |
| `UNIT` | States the unit independently of the magnitude. |
| `MODEL` | Names the provenance-model registry entry. |
| `END` | Closes the claim. |

The register uses only Losica's existing `root`, `relator`, and
`clause_operator` classes. It adds no grammatical class.

## Exact example

The source fact “mean solar day” uses this expanded expression:

```text
mean-over(
  of(time,
     return(of(direction, between(of(surface, planet), star)),
            same(direction))),
  one(around(planet, star)))
```

Compact Losica is:

```text
qaplat umlu katquk timap mitli mik kipqut mitli ikqik timqa mitli pumluk katquk rukrat pit ikqik qat lirmat katquk rukrat 8.556787177492277 quran napat papnir
```

Its broad phonemic IPA is:

```text
/kʼap.lat um.lu kat.kʼuk ti.map mit.li mik kip.kʼut mit.li ik.kʼik tim.kʼa mit.li pum.luk kat.kʼuk ruk.rat pit ik.kʼik kʼat lir.mat kat.kʼuk ruk.rat pan.tar ak.lum ki.rur ki.rur kʼap.tip mu.par pan.tar mu.par tun.kit mu.par mu.par am.ni ra.tan tim.lir tim.lir mu.par mu.par kʼu.ran na.pat pap.nir/
```

The numeral is one compact written token but the IPA renders every character
with its reversible spoken form. Running `analyze` lists every word's IPA,
semantic ID, arity, syntactic role, and exact semantic burden.

## Inverse and failure behavior

For every included fact, both compact and fully spoken encodings satisfy:

```text
decode(encode(record)) == record
```

The decoder also checks that the recovered tree names a registered source
field. It rejects an unknown word, an incomplete tree, trailing expression
material, a grammatical but unregistered tree, a mismatched quantity ID,
category swaps, noncanonical decimals, and invalid null/evidence combinations.
The 22 old opaque forms are reserved and cannot be silently reassigned.

## Build and inspect

```bash
python BUILD_PLANETARY_REGISTER.py --out planetary-register.json
python USE_PLANETARY_REGISTER.py planetary-register.json expression quantity:semimajor_axis
python USE_PLANETARY_REGISTER.py planetary-register.json say fact:mean_solar_day
python USE_PLANETARY_REGISTER.py planetary-register.json say fact:mean_solar_day --spoken-numbers
python USE_PLANETARY_REGISTER.py planetary-register.json analyze "LOSICA CLAIM"
```

Unknown material fails closed instead of receiving a plausible-sounding
meaning.
