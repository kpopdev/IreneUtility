from ..Base import Base


# noinspection PyBroadException,PyPep8
class Patreon(Base):
    def __init__(self, *args):
        super().__init__(*args)
    
    async def get_patreon_users(self):
        """Get the permanent patron users"""
        return await self.ex.conn.fetch("SELECT userid from patreon.users")

    async def get_patreon_role_members(self, super_patron=False):
        """Get the members in the patreon roles."""
        support_guild = self.ex.client.get_guild(int(self.ex.keys.bot_support_server_id))
        # API call will not show role.members
        if not super_patron:
            patreon_role = support_guild.get_role(int(self.ex.keys.patreon_role_id))
        else:
            patreon_role = support_guild.get_role(int(self.ex.keys.patreon_super_role_id))
        return patreon_role.members

    async def check_if_patreon(self, user_id, super_patron=False):
        """Check if the user is a patreon.
        There are two ways to check if a user ia a patreon.
        The first way is getting the members in the Patreon/Super Patreon Role.
        The second way is a table to check for permanent patreon users that are directly added by the bot owner.
        -- After modifying -> We take it straight from cache now.
        """
        user = await self.ex.get_user(user_id)
        if super_patron:
            return user.super_patron
        return user.patron

    async def add_to_patreon(self, user_id):
        """Add user as a permanent patron."""
        try:
            user_id = int(user_id)
            await self.ex.conn.execute("INSERT INTO patreon.users(userid) VALUES($1)", user_id)
            user = await self.ex.get_user(user_id)
            user.patron = True
            user.super_patron = True
        except:
            pass

    async def remove_from_patreon(self, user_id):
        """Remove user from being a permanent patron."""
        try:
            user_id = int(user_id)
            await self.ex.conn.execute("DELETE FROM patreon.users WHERE userid = $1", user_id)
            user = await self.ex.get_user(user_id)
            user.patron = False
            user.super_patron = False
        except:
            pass

    async def reset_patreon_cooldown(self, ctx):
        """Checks if the user is a patreon and resets their cooldown."""
        # Super Patrons also have the normal Patron role.
        if await self.check_if_patreon(ctx.author.id):
            ctx.command.reset_cooldown(ctx)


# self.ex.u_patreon = Patreon()
