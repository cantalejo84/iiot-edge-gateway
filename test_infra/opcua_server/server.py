import asyncio
import random
import logging
from asyncua import Server, ua

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    server = Server()
    await server.init()
    server.set_endpoint("opc.tcp://0.0.0.0:4840/freeopcua/server/")
    server.set_server_name("IIoT Test OPC UA Server")

    uri = "urn:iiot-test-server"
    idx = await server.register_namespace(uri)

    objects = server.nodes.objects

    # Plant object
    plant = await objects.add_object(idx, "Plant")

    # Line 1
    line1 = await plant.add_object(idx, "Line1")
    l1_temp = await line1.add_variable(idx, "Temperature", 25.0, ua.VariantType.Double)
    l1_pressure = await line1.add_variable(idx, "Pressure", 3.0, ua.VariantType.Double)
    l1_speed = await line1.add_variable(idx, "Speed", 300, ua.VariantType.Int32)
    l1_status = await line1.add_variable(idx, "Status", True, ua.VariantType.Boolean)

    # Line 2
    line2 = await plant.add_object(idx, "Line2")
    l2_temp = await line2.add_variable(idx, "Temperature", 22.0, ua.VariantType.Double)
    l2_pressure = await line2.add_variable(idx, "Pressure", 2.5, ua.VariantType.Double)
    l2_speed = await line2.add_variable(idx, "Speed", 250, ua.VariantType.Int32)
    l2_status = await line2.add_variable(idx, "Status", True, ua.VariantType.Boolean)

    # Utilities
    utilities = await plant.add_object(idx, "Utilities")
    power = await utilities.add_variable(idx, "PowerConsumption", 150.0, ua.VariantType.Double)
    water = await utilities.add_variable(idx, "WaterFlow", 45.0, ua.VariantType.Double)

    # Make variables writable (for testing)
    for var in [l1_temp, l1_pressure, l1_speed, l1_status,
                l2_temp, l2_pressure, l2_speed, l2_status,
                power, water]:
        await var.set_writable()

    logger.info("Starting OPC UA Test Server at opc.tcp://0.0.0.0:4840")

    async with server:
        while True:
            # Simulate changing values
            await l1_temp.write_value(round(random.uniform(20.0, 35.0), 2))
            await l1_pressure.write_value(round(random.uniform(1.0, 5.0), 2))
            await l1_speed.write_value(ua.Variant(random.randint(100, 500), ua.VariantType.Int32))
            await l1_status.write_value(random.choice([True, True, True, False]))

            await l2_temp.write_value(round(random.uniform(18.0, 30.0), 2))
            await l2_pressure.write_value(round(random.uniform(1.5, 4.5), 2))
            await l2_speed.write_value(ua.Variant(random.randint(150, 450), ua.VariantType.Int32))
            await l2_status.write_value(random.choice([True, True, True, False]))

            await power.write_value(round(random.uniform(100.0, 300.0), 2))
            await water.write_value(round(random.uniform(30.0, 60.0), 2))

            await asyncio.sleep(2)


if __name__ == "__main__":
    asyncio.run(main())
