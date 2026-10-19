from app.config import ENTITY_TYPES
from app.generator import TEMPLATES, SyntheticGenerator, generate_samples


def test_spans_point_at_the_planted_values():
    gen = SyntheticGenerator(seed=1)
    for template in TEMPLATES:
        sample = gen.fill(template)
        assert "{" not in sample.text, "every placeholder should be filled"
        for span in sample.spans:
            value = sample.text[span.start:span.end]
            assert value.strip() == value and value, f"bad span {span} in {sample.text!r}"


def test_same_seed_gives_same_data():
    a = [s.to_dict() for s in generate_samples(20, seed=7)]
    b = [s.to_dict() for s in generate_samples(20, seed=7)]
    assert a == b


def test_different_seed_gives_different_data():
    assert generate_samples(5, seed=1)[0].text != generate_samples(5, seed=2)[0].text


def test_every_entity_type_is_generated():
    types = {s.entity_type for sample in generate_samples(300) for s in sample.spans}
    assert types == set(ENTITY_TYPES)
