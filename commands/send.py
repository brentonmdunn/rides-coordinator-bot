import random

async def execute(message, needs_ride, RIDES_MESSAGE, REACTS):
    # Clears list before each reaction
    needs_ride = []

    sent_message = await message.channel.send(RIDES_MESSAGE)
    message_id = sent_message.id

    # Adds random reaction for ride
    current_reaction = random.randint(0, len(REACTS) - 1)
    await sent_message.add_reaction(REACTS[current_reaction])
    print(current_reaction)