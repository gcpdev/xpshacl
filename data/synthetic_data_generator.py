from rdflib import Graph, URIRef, Literal, Namespace, BNode
from rdflib.namespace import RDF, XSD, SH as sh
import random
from faker import Faker

fake = Faker()

ex = Namespace("http://xpshacl.org/#")
sh = Namespace("http://www.w3.org/ns/shacl#")


def generate_complex_data(num_items=10000):
    g = Graph()
    for i in range(num_items):
        item = ex[f"item{i}"]
        g.add((item, RDF.type, ex.Resource))
        g.add(
            (
                item,
                ex.integerValue,
                Literal(random.randint(0, 200), datatype=XSD.integer),
            )
        )
        g.add((item, ex.stringValue, Literal(fake.word())))
        g.add((item, ex.dateValue, Literal(fake.date(), datatype=XSD.date)))
        g.add((item, ex.languageValue, Literal(fake.sentence(), lang="en")))
        g.add((item, ex.listValue, ex[f"list{i}"]))
        g.add((ex[f"list{i}"], RDF.first, Literal(random.randint(1, 10))))
        g.add((ex[f"list{i}"], RDF.rest, RDF.nil))

        # Recursive data
        if random.random() < 0.2:
            g.add((item, ex.recursiveValue, ex[f"recursive{i}"]))
            g.add((ex[f"recursive{i}"], ex.nestedValue, Literal(fake.word())))

        # NodeKind variations
        if random.random() < 0.1:
            g.add((item, ex.blankNodeValue, BNode()))
        if random.random() < 0.1:
            g.add((item, ex.literalValue, Literal("test", datatype=XSD.string)))

        # Introduce random violations
        if random.random() < 0.1:
            g.remove((item, ex.integerValue, None))
            g.add((item, ex.integerValue, Literal("invalid")))
        if random.random() < 0.1:
            g.add(
                (
                    item,
                    ex.stringValue,
                    Literal("1234567890123456789012345678901234567890"),
                )
            )
        if random.random() < 0.05:
            g.remove((item, ex.languageValue, None))
            g.add((item, ex.languageValue, Literal(fake.sentence(), lang="fr")))
        if random.random() < 0.05:
            g.remove((item, ex.listValue, None))
            g.add((item, ex.listValue, ex[f"invalidList{i}"]))

    g.bind("ex", ex)
    g.bind("xsd", XSD)
    return g


def generate_complex_shapes(g_shapes):
    resource_shape = ex.ResourceShape
    g_shapes.add((resource_shape, RDF.type, sh.NodeShape))
    g_shapes.add((resource_shape, sh.targetClass, ex.Resource))

    # Integer constraint
    int_prop = ex.IntegerPropertyShape
    g_shapes.add((resource_shape, sh.property, int_prop))
    g_shapes.add((int_prop, sh.path, ex.integerValue))
    g_shapes.add((int_prop, sh.datatype, XSD.integer))
    g_shapes.add((int_prop, sh.minInclusive, Literal(10)))
    g_shapes.add((int_prop, sh.maxInclusive, Literal(150)))

    # String constraint
    string_prop = ex.StringPropertyShape
    g_shapes.add((resource_shape, sh.property, string_prop))
    g_shapes.add((string_prop, sh.path, ex.stringValue))
    g_shapes.add((string_prop, sh.minLength, Literal(3)))
    g_shapes.add((string_prop, sh.maxLength, Literal(20)))
    g_shapes.add((string_prop, sh.pattern, Literal(r"^[a-zA-Z]+$")))

    # Date constraint
    date_prop = ex.DatePropertyShape
    g_shapes.add((resource_shape, sh.property, ex.DatePropertyShape))
    g_shapes.add((ex.DatePropertyShape, sh.path, ex.dateValue))
    g_shapes.add((ex.DatePropertyShape, sh.datatype, XSD.date))

    # Language constraint
    lang_prop = ex.LanguagePropertyShape
    g_shapes.add((resource_shape, sh.property, ex.LanguagePropertyShape))
    g_shapes.add((ex.LanguagePropertyShape, sh.path, ex.languageValue))
    g_shapes.add((ex.LanguagePropertyShape, sh.languageIn, Literal("en")))

    # List constraint
    list_prop = ex.ListPropertyShape
    g_shapes.add((resource_shape, sh.property, ex.ListPropertyShape))
    g_shapes.add((ex.ListPropertyShape, sh.path, ex.listValue))
    g_shapes.add((ex.ListPropertyShape, sh.nodeKind, sh.IRI))

    # Recursive constraint
    recursive_shape = ex.RecursiveShape
    g_shapes.add((resource_shape, sh.property, recursive_shape))
    g_shapes.add((recursive_shape, sh.path, ex.recursiveValue))
    g_shapes.add((recursive_shape, sh.nodeKind, sh.IRI))

    # NodeKind constraints
    blank_node_shape = ex.BlankNodeShape
    g_shapes.add((resource_shape, sh.property, blank_node_shape))
    g_shapes.add((blank_node_shape, sh.path, ex.blankNodeValue))
    g_shapes.add((blank_node_shape, sh.nodeKind, sh.BlankNode))

    literal_node_shape = ex.LiteralNodeShape
    g_shapes.add((resource_shape, sh.property, literal_node_shape))
    g_shapes.add((literal_node_shape, sh.path, ex.literalValue))
    g_shapes.add((literal_node_shape, sh.nodeKind, sh.Literal))

    # Logical constraint examples
    # OR
    or_shape = ex.OrShape
    g_shapes.add((resource_shape, sh.OrConstraintComponent, or_shape))
    g_shapes.add((or_shape, RDF.first, ex.IntegerPropertyShape))
    g_shapes.add((or_shape, RDF.rest, ex[f"or_rest"]))
    g_shapes.add((ex[f"or_rest"], RDF.first, ex.StringPropertyShape))
    g_shapes.add((ex[f"or_rest"], RDF.rest, RDF.nil))

    # NOT
    not_shape = ex.NotShape
    g_shapes.add((resource_shape, sh.NotConstraintComponent, not_shape))
    g_shapes.add((ex.NotPropertyShape, sh.path, ex.dateValue))

    # XONE
    xone_shape = ex.XoneShape
    g_shapes.add((resource_shape, sh.XoneConstraintComponent, xone_shape))
    g_shapes.add((xone_shape, RDF.first, ex.IntegerPropertyShape))
    g_shapes.add((xone_shape, RDF.rest, ex[f"xone_rest"]))
    g_shapes.add((ex[f"xone_rest"], RDF.first, ex.StringPropertyShape))
    g_shapes.add((ex[f"xone_rest"], RDF.rest, RDF.nil))

    # SPARQL constraint examples
    sparql_shape_even = ex.SparqlShapeEven
    g_shapes.add((resource_shape, sh.PropertyConstraintComponent, sparql_shape_even))
    g_shapes.add((sparql_shape_even, sh.path, ex.integerValue))
    g_shapes.add((sparql_shape_even, sh.sparql, ex.SparqlConstraintEven))
    g_shapes.add(
        (ex.SparqlConstraintEven, sh.message, Literal("Integer value must be even."))
    )
    g_shapes.add(
        (
            ex.SparqlConstraintEven,
            sh.select,
            Literal("SELECT $this WHERE { FILTER ( ($this % 2) != 0 ) }"),
        )
    )

    sparql_shape_length = ex.SparqlShapeLength
    g_shapes.add((resource_shape, sh.PropertyConstraintComponent, sparql_shape_length))
    g_shapes.add((sparql_shape_length, sh.path, ex.stringValue))
    g_shapes.add((sparql_shape_length, sh.sparql, ex.SparqlConstraintLength))
    g_shapes.add(
        (
            ex.SparqlConstraintLength,
            sh.message,
            Literal("String length must be greater than 5."),
        )
    )
    g_shapes.add(
        (
            ex.SparqlConstraintLength,
            sh.select,
            Literal("SELECT $this WHERE { FILTER ( STRLEN($this) <= 5 ) }"),
        )
    )

    g_shapes.bind("sh", sh)
    g_shapes.bind("ex", ex)
    g_shapes.bind("xsd", XSD)
    return g_shapes


def main():
    data_graph = generate_complex_data()
    shapes_graph = Graph()
    shapes_graph = generate_complex_shapes(shapes_graph)

    data_graph.serialize("complex_data.ttl", format="turtle")
    shapes_graph.serialize("complex_shapes.ttl", format="turtle")


if __name__ == "__main__":
    main()
