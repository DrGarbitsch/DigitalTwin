"""Writes through a plain OPC UA client, like a machine changing its values."""
import asyncio
import datetime
import sys
from asyncua import Client, ua

V = ua.VariantType
SETS = {
    'all': [
        ('i=6020', 71.25, V.Double),
        ('i=6119', 17, V.UInt32),
        ('i=6029', True, V.Boolean),
        ('i=6023', 'with "quotes"', V.String),
        ('i=6101', datetime.datetime(2025, 7, 14, 8, 30, tzinfo=datetime.timezone.utc), V.DateTime),
        ('i=6097', 1, V.Int32),
        ('i=6095', ua.OptionSet(Value=b'\x01\x00', ValidBits=b'\x80\x0f'), None),
    ],
    'after': [('i=6020', 42.5, V.Double)],
}


async def main():
    async with Client('opc.tcp://127.0.0.1:4840/') as client:
        index = await client.get_namespace_index('http://yourorganisation.org/InstanceExample/')
        for nodeid, value, kind in SETS[sys.argv[1]]:
            variant = ua.Variant(value, kind) if kind else ua.Variant(value)
            await client.get_node(f'ns={index};{nodeid}').write_value(ua.DataValue(variant))


asyncio.run(main())
