"""
Modbus TCP demo server for IIoT Edge Gateway.
Simulates industrial registers: temperature, pressure, motor speed, voltage, current.
Values fluctuate every 2 seconds. Uses FLOAT32 (2 registers each, ABCD byte order).

Register map (holding registers, 0-based):
  0-1  : temperature  (°C)    20.0 – 30.0
  2-3  : pressure     (bar)   1.0  – 5.0
  4-5  : motor_speed  (RPM)   1000 – 1500
  6-7  : voltage      (V)     220  – 240
  8-9  : current      (A)     5.0  – 15.0
"""

import asyncio
import logging
import math
import struct
import time

from pymodbus.datastore import (
    ModbusSequentialDataBlock,
    ModbusServerContext,
    ModbusSlaveContext,
)
from pymodbus.server import StartAsyncTcpServer

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

PORT = 502
SLAVE_ID = 1


def float_to_regs(value: float) -> list[int]:
    """Pack a float32 into two 16-bit registers (ABCD / big-endian)."""
    packed = struct.pack(">f", value)
    hi = struct.unpack(">H", packed[0:2])[0]
    lo = struct.unpack(">H", packed[2:4])[0]
    return [hi, lo]


def build_holding_registers() -> list[int]:
    t = time.time()
    temperature = 25.0 + 5.0 * math.sin(t / 10)
    pressure = 3.0 + 2.0 * math.sin(t / 7 + 1)
    motor_speed = 1250 + 250 * math.sin(t / 5 + 2)
    voltage = 230.0 + 10.0 * math.sin(t / 13 + 3)
    current = 10.0 + 5.0 * math.sin(t / 8 + 4)

    regs = []
    for val in [temperature, pressure, motor_speed, voltage, current]:
        regs.extend(float_to_regs(val))
    # Pad to 100 registers so any address read works
    regs += [0] * (100 - len(regs))
    return regs


async def update_loop(context: ModbusServerContext):
    """Update register values every 2 seconds."""
    while True:
        regs = build_holding_registers()
        context[SLAVE_ID].setValues(3, 0, regs)  # function code 3 = holding registers
        await asyncio.sleep(2)


async def main():
    regs = build_holding_registers()
    store = ModbusSlaveContext(
        hr=ModbusSequentialDataBlock(0, regs),
    )
    context = ModbusServerContext(slaves={SLAVE_ID: store}, single=False)

    logger.info(
        "Modbus TCP demo server starting on port %d (slave ID %d)", PORT, SLAVE_ID
    )
    logger.info(
        "Registers: temperature(0), pressure(2), motor_speed(4), voltage(6), current(8)"
    )

    asyncio.create_task(update_loop(context))

    await StartAsyncTcpServer(context=context, address=("0.0.0.0", PORT))


if __name__ == "__main__":
    asyncio.run(main())
