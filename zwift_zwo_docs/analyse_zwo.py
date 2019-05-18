"""
Scan Zwift Workout (.zwo) files and aggregate their tag and attribute usage

usage: analyse_zwo [options] <workouts-dir>

Options:
    --json  Output JSON
"""
import io
from collections import Counter
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

import docopt
from lxml import etree


def parse_zwo(path):
    try:
        etree.parse(path)
    except etree.XMLSyntaxError as e:
        if 'xmlParseEntityRef: no name' not in str(e):
            raise

    # Some ZWO files have unescaped ampersands...
    with open(path, 'rb') as f:
        content = f.read()
        content = content.replace(b' & ', b' &amp; ')
        return etree.parse(io.BytesIO(content), base_url=path)


def list_zwo_file_paths(root_dir):
    for dirpath, dirnames, filenames in os.walk(root_dir):
        dirpath = Path(dirpath)
        yield from (dirpath / f for f in filenames
                     if re.match(r'.*\.(?:xml|zwo)$', f))


def list_tag_attribute_usage(tree: etree._ElementTree):
    def generate_tag_attr_paths(element, parent_path):
        children = list(element.iterchildren(tag=etree.Element))
        value = (element.text
                 if (len(children) == 0 and element.text
                     and element.text.strip()) else None)
        attrs = {k: v for k, v in element.attrib.items()
                 # Ignore namespaced attributes
                 if not k.startswith('{')}
        yield parent_path, element.tag, attrs, value
        path = parent_path + (element.tag,)

        for child_el in children:
            yield from generate_tag_attr_paths(child_el, path)

    yield from generate_tag_attr_paths(tree.getroot(), ())


def analyse_datatype(value_counts):
    if all(re.match(r'^\d+$', val) for val in value_counts):
        datatype = 'integer'
    elif all(re.match(r'^\d+(?:\.\d*)?$', val) for val in value_counts):
        datatype = 'real'
    else:
        datatype = 'string'

    def key(vc):
        value, count = vc
        return count

    total_occurrences = sum(value_counts.values())
    highest_freq_value = max(value_counts.values()) / total_occurrences

    # Sample values are intended to demonstrate the values that can be used
    # when the value is one of a small set of options. E.g. always 1 or 0.
    # It should ignore things like <name> which will almost always be different.
    sample_values = [
        (value, count / total_occurrences)
        for value, count in sorted(value_counts.items(), reverse=True, key=key)
        if (count / total_occurrences) >= 0.05 or highest_freq_value > 0.1][:10]

    return {'datatype': datatype, 'value_samples': {
        'exhaustive': len(sample_values) == len(value_counts),
        'values': sample_values,
        'total_occurrences': total_occurrences
    }}


def render_value_analysis(val):

    samples = val['value_samples']['values']
    if len(samples) > 0:
        samples_label = ('all values' if val['value_samples']['exhaustive']
                         else 'most frequent values')
        rendered_samples = f', {samples_label}:\n' + '\n'.join(
            f'      - {freq * 100: 6.2f}% => {value!r}' for value, freq in samples
        )
    else:
        rendered_samples = ''
    datatype = val['datatype']
    occurrences = val['value_samples']['total_occurrences']
    return (f'datatype: {datatype}, occurrences: {occurrences}'
            f'{rendered_samples}')


def aggregate_tag_attribute_usage(tag_attr_paths):
    tags = defaultdict(lambda: {'paths': set(),
                                'attributes': set(),
                                'value': Counter()})
    # Assume attributes used across different elements have the same semantics
    attributes = defaultdict(lambda: {
        'tags': set(),
        'values': Counter()
    })

    for path, tag, attrs, value in tag_attr_paths:
        tags[tag]['paths'].add(path)
        tags[tag]['attributes'].update(attrs.keys())
        for attr, attr_val in attrs.items():
            attributes[attr]['tags'].add(tag)
            attributes[attr]['values'][attr_val] += 1
        if value is not None:
            tags[tag]['value'][value] += 1

    return {
        'elements': [
            {
                'tag': tag,
                'paths': sorted(tags[tag]['paths']),
                'attributes': sorted(tags[tag]['attributes']),
                'value': (analyse_datatype(tags[tag]['value'])
                          if tags[tag]['value'] else None)
            }
            for tag in sorted(tags.keys())
        ],
        'attributes': [
            {
                'attribute': attribute,
                'tags': sorted(attributes[attribute]['tags']),
                'value': analyse_datatype(attributes[attribute]['values'])
            }
            for attribute in sorted(attributes.keys())
        ]
    }


def main():
    args = docopt.docopt(__doc__)

    tag_attr_usages = (
        usage
        for path in list_zwo_file_paths(args['<workouts-dir>'])
        for usage in list_tag_attribute_usage(parse_zwo(str(path))))

    tag_attr_usage = aggregate_tag_attribute_usage(tag_attr_usages)

    if args['--json']:
        json.dump(tag_attr_usage, sys.stdout, indent=2)
        print()
    else:
        elements = tag_attr_usage['elements']
        attributes = tag_attr_usage['attributes']

        print('## Tags ##\n')

        for el in elements:
            paths = ' '.join(['/' + '/'.join(path) for path in el['paths']])
            attrs = ' '.join(el['attributes'])
            print(f'  <{el["tag"]}>:')
            print(f'    paths: {paths}')
            print(f'    attrs: {attrs}')
            if el['value'] is not None:
                print(f'    values: {render_value_analysis(el["value"])}')

        print('\n## Attributes ##\n')

        for attr in attributes:
            value_info = render_value_analysis(attr['value'])
            print(f'  {attr["attribute"]}="..."')
            print(f'    tags: {" ".join(attr["tags"])}')
            print(f'    values: {value_info}')


if __name__ == '__main__':
    main()
