import utils.ping as ping

async def execute(message, message_id, bot_name):
    if message_id is None:
        await message.channel.send("Message has not sent yet.")
        return
    target_message = await message.channel.fetch_message(message_id)

    reaction_users = set()
    for reaction in target_message.reactions:
        async for user in reaction.users():
            if str(user) == bot_name:
                continue
            reaction_users.add(user)

    users_list = ", ".join(ping.get_member(message.guild.members, str(user)).mention for user in reaction_users)
    await message.channel.send(f"Users who reacted: {users_list}")