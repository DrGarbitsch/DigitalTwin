"""The contract of the dataservice's messages. Fails on the bugs this chain has really had."""
import json
import sys

P = 'http://opcfoundation.org/UA/Pumps/'
messages = [json.loads(line) for line in open(sys.argv[1])]
last = {m['n'].rsplit('/', 1)[-1]: m for m in messages}


def check(ok, text):
    print(('ok   ' if ok else 'FAIL ') + text)
    if not ok:
        sys.exit(1)


check(len(last) == 40, f'distinct attributes sent: {len(last)}, the 6 unset nodes send nothing')
check(not any(m['v'] == 'None' for m in messages), 'no value is the string None')
check(all(m['t'] in ('Property', 'IriProperty', 'JsonProperty', 'Relationship') for m in messages), 'only known labels')
check(all('/' not in m['i'] for m in messages), 'no / in an entity id')
check(last['hasMotorTemperature']['v'] == '71.25', 'number')
check(last['hasNumberOfStarts']['v'] == '17', 'UInt32')
check(last['hasRotorBlocked']['v'] == 'true', 'lowercase boolean')
check(last['hasTechnicalDataLink']['v'] == 'with "quotes"', 'quotes survive the JSON message')
check(last['hasInstallationDate']['v'].startswith('2025-07-14T08:30:00'), 'ISO timestamp')
check(last['hasPumpClass']['v'] == P + 'PositiveDisplacementPump' and last['hasPumpClass']['t'] == 'IriProperty', 'enum is an IRI')
modes = last['hasOfferedControlModes']
check(modes['t'] == 'JsonProperty' and json.loads(modes['v'])['xsd:Body']['xsd:OptionSet']['xsd:Value'] == 'AQA=', 'structure is JSON')
check('hasOnOff' not in last, 'unset node sends nothing')
