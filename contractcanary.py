"""Authored JSON contracts and local migrations, NOT Confluent serializers/rules."""
import argparse
import copy
import json
from pathlib import Path

VERSIONS = (1, 2, 3)
SCALE = {'USD': 100, 'JPY': 1}
FIELDS = {1: 'customer_id', 2: 'customer_id', 3: 'customer'}

class Unsupported(ValueError):
    pass


def check_version(version):
    if type(version) is not int or version not in VERSIONS:
        raise Unsupported('supported versions: 1, 2, 3')


def project(event, version):
    """Small declared reader schema: exact primitive types, rename has default ''."""
    check_version(version)
    if type(event) is not dict:
        raise ValueError('event object required')
    required = {'amount': int, 'currency': str}
    for key, typ in required.items():
        if type(event.get(key)) is not typ:
            raise ValueError('invalid '+key)
    customer = event.get(FIELDS[version], '')
    discount = event.get('discount')
    if type(customer) is not str or (discount is not None and type(discount) is not int):
        raise ValueError('invalid customer or discount')
    return dict(amount=event['amount'], currency=event['currency'],
                discount=discount, **{FIELDS[version]: customer})


def meaning(event, version):
    value = project(event, version)
    if value['currency'] not in SCALE:
        raise Unsupported('currency outside authored scale catalog')
    scale = SCALE[value['currency']] if version == 1 else 1
    return {'currency': value['currency'],
            'net_minor': (value['amount']-(value['discount'] or 0))*scale,
            'customer': value[FIELDS[version]]}


def wire(event):
    return json.loads(json.dumps(event, allow_nan=False, sort_keys=True))


def migrate(event, source, target, defect='none'):
    check_version(source)
    check_version(target)
    if defect not in {'none', 'units', 'identity', 'discount'}:
        raise Unsupported('unknown migration configuration')
    if abs(source-target) != 1:
        raise Unsupported('only adjacent migration edges are registered')
    value = project(wire(event), source)
    if {source, target} == {1, 2}:
        scale = 100 if defect == 'units' else SCALE.get(value['currency'])
        if scale is None:
            raise Unsupported('unknown currency')
        for key in ('amount', 'discount'):
            if value[key] is None:
                continue
            if source == 1:
                value[key] *= scale
            else:
                if value[key] % scale:
                    raise Unsupported('v1 cannot exactly represent fractional major units')
                value[key] //= scale
    else:
        identity = value.pop(FIELDS[source])
        value[FIELDS[target]] = '' if defect == 'identity' else identity
    if defect == 'discount' and target == 1:
        value['discount'] = None
    return wire(value)


def experiment(event, path, *, defect='none', client='json-migrations', migrations=True):
    if not isinstance(path, list) or not path:
        raise ValueError('nonempty version path required')
    for version in path:
        check_version(version)
    if client not in {'json-migrations', 'json-no-rules'}:
        return {'status': 'unsupported', 'reason': 'unimplemented client/serialization format'}
    expected = meaning(event, path[0])
    value = wire(project(event, path[0]))
    try:
        for source, target in zip(path, path[1:]):
            if source == target:
                continue
            if migrations:
                if client != 'json-migrations':
                    raise Unsupported('client cannot execute migration rules')
                value = migrate(value, source, target, defect)
            else:
                value = project(wire(value), target)
        observed = meaning(value, path[-1])
    except Unsupported as error:
        return {'status': 'unsupported', 'reason': str(error)}
    violations = [key for key in expected if expected[key] != observed[key]]
    return {'status': 'violation' if violations else 'pass', 'structural_pass': True,
            'violations': violations, 'expected': expected, 'observed': observed,
            'wire_event': value}


def minimize(event, path, **options):
    """Greedy deterministic 1-minimal witness over field deletion/value shrink/path removal."""
    event, path = copy.deepcopy(event), list(path)
    def fails(e, p):
        try:
            return experiment(e, p, **options)['status'] == 'violation'
        except (ValueError, Unsupported):
            return False
    if not fails(event, path):
        raise ValueError('a semantic violation is required')
    changed = True
    while changed:
        changed = False
        for key in list(event):
            trial = {k: v for k, v in event.items() if k != key}
            if fails(trial, path):
                event, changed = trial, True
        for key in ('amount', 'discount'):
            if type(event.get(key)) is int and event[key] not in (0, 1):
                for small in (0, 1):
                    trial = dict(event, **{key: small})
                    if fails(trial, path):
                        event, changed = trial, True
                        break
        for i in range(1, len(path)-1):
            trial = path[:i]+path[i+1:]
            if fails(event, trial):
                path, changed = trial, True
                break
    return {'event': event, 'path': path, 'result': experiment(event, path, **options),
            'minimality': 'greedy field/value/internal-path reductions; not global minimum'}


def demo():
    rows = []
    for currency in SCALE:
        for discount in (None, 2):
            for source in VERSIONS:
                event = dict(amount=10*(SCALE[currency] if source != 1 else 1), currency=currency,
                             discount=None if discount is None else discount*(SCALE[currency] if source != 1 else 1),
                             **{FIELDS[source]: 'buyer-7'})
                for target in VERSIONS:
                    direction = 1 if target >= source else -1
                    path = list(range(source, target+direction, direction))
                    for defect in ('none', 'units', 'identity', 'discount'):
                        rows.append(dict(source=source, target=target, currency=currency,
                                         discount=discount, defect=defect,
                                         result=experiment(event, path, defect=defect),
                                         structural_only=experiment(event, path, migrations=False)))
    witness = dict(amount=987, currency='JPY', discount=None, customer_id='buyer-7', debug='irrelevant')
    return {'scope': 'authored JSON wire model; no Kafka/Schema Registry/Avro execution',
            'cases': len(rows), 'safe_failures': sum(r['defect']=='none' and r['result']['status']!='pass' for r in rows),
            'semantic_violations': sum(r['result']['status']=='violation' for r in rows),
            'structural_baseline_misses': sum(r['structural_only']['status']=='violation' for r in rows if r['defect']=='none'),
            'counterexample': minimize(witness, [1,2], defect='units'), 'matrix': rows,
            'unsupported_controls': [experiment(witness,[1,2],client='protobuf'), experiment(witness,[1,2],client='json-no-rules')]}

if __name__ == '__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--output',type=Path); args=parser.parse_args()
    result=json.dumps(demo(),indent=2)+'\n'
    if args.output: args.output.write_text(result)
    else: print(result,end='')
