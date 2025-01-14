import concurrent.futures

from .util import u_exceptions, u_logger as log, u_local_cache
from typing import TYPE_CHECKING
from discord.ext.commands import Context
from Weverse import WeverseClientAsync
import discord
import random
import asyncio
import os
import tweepy
from . import models, s_sql, util, Base
from typing import List


# do not import in runtime. This is used for type-hints.
if TYPE_CHECKING:
    from aiohttp import ClientSession

"""
Utility.py
Resource Center for Irene -> Essentially serves as a Utility for Irene.
Any potentially useful/repeated functions will end up here
All categorized utility methods will be placed as objects prefixed with u_ as a property.
"""


# noinspection PyBroadException,PyPep8
class Utility:
    def __init__(self, keys=None, db_connection=None, events=None, d_py_client=None, aiohttp_session=None,
                 weverse_client=None, create_db_structure=False):
        """
        :param keys:  Access to the key file
        :param db_connection:  DB Connection
        :param events:  Client-Sided Events class
        :param d_py_client: Discord.py client (Assumed to be an AutoShardedClient)
        :param aiohttp_session: Aiohttp client session
        :param weverse_client: Weverse client
        :param create_db_structure: whether to create db structure on run.
        """
        # A lot of these properties may be created via client side
        # in order to make Utility more portable when needed and client friendly.
        self.test_bot = None  # this is changed on the client side in run.py
        self.upload_from_host = False  # this is changed on the client side in run.py
        self.client: discord.AutoShardedClient = d_py_client  # discord.py client
        self.session: ClientSession = aiohttp_session  # aiohttp client session
        self.conn = db_connection  # db connection
        self.create_db_structure: bool = create_db_structure  # whether to create db structure on run.

        # Set to True if not on the production server (useful if testing ex.test_bot as False).
        # This was initially created to not flood datadog with incorrect input while ex.test_bot was False
        self.dev_mode = True

        # Set to True if you intend to have announcement text channels on the support server and would like
        # the weverse updates command to be private only to the bot owner. This should be specified on client side.
        # this will also Publish (as an announcement) every single message if set to True.
        self.weverse_announcements: bool = False

        # Set to False if you do not want the cache to reset itself every 12 hours.
        self.reset_cache: bool = True

        s_sql.self.conn = self.conn  # update our SQL connection.
        util_args = {self}

        self.discord_cache_loaded = False  # d.py library cache finished loading
        self.irene_cache_loaded = False  # IreneBot cache finished loading
        self.cache = u_local_cache.Cache(*util_args)  # instance for loaded cache
        self.temp_patrons_loaded = False
        self.running_loop = None  # current asyncio running loop
        # self.thread_pool = None  # ThreadPoolExecutor for operations that block the event loop.
        self.keys: models.Keys = keys  # access to keys file

        self.api: tweepy.API = None
        self.loop_count = 0
        self.recursion_limit = 10000
        self.api_issues = 0  # api issues in a given minute
        self.max_idol_post_attempts = 10  # 100 was too much
        self.twitch_guild_follow_limit = 2

        self.weverse_client: WeverseClientAsync = weverse_client

        self.exceptions = u_exceptions  # custom error handling
        self.twitch_token = None  # access tokens are set everytime the token is refreshed.

        self.events = events  # Client-Sided Events class

        
        """
        IMPORTANT: This design implementation is a hack for circular imports.
        The intended use is to allow a singular object to manage the entire Utility.
        """
        # Sub-Utils to allow branching methods from this individual Utility object.

        self.u_database = util.u_database.DataBase(*util_args)
        self.u_cache = util.u_cache.Cache(*util_args)
        self.u_miscellaneous = util.u_miscellaneous.Miscellaneous(*util_args)
        self.u_blackjack = util.u_blackjack.BlackJack(*util_args)
        self.u_group_members = util.u_groupmembers.GroupMembers(*util_args)
        self.u_logging = util.u_logging.Logging(*util_args)
        self.u_twitter = util.u_twitter.Twitter(*util_args)
        self.u_last_fm = util.u_lastfm.LastFM(*util_args)
        self.u_patreon = util.u_patreon.Patreon(*util_args)
        self.u_moderator = util.u_moderator.Moderator(*util_args)
        self.u_custom_commands = util.u_customcommands.CustomCommands(*util_args)
        self.u_bias_game = util.u_biasgame.BiasGame(*util_args)
        self.u_data_dog = util.u_datadog.DataDog(*util_args)
        self.u_weverse = util.u_weverse.Weverse(*util_args)
        self.u_self_assign_roles = util.u_selfassignroles.SelfAssignRoles(*util_args)
        self.u_reminder = util.u_reminder.Reminder(*util_args)
        self.u_guessinggame = util.u_guessinggame.GuessingGame(*util_args)
        self.u_twitch = util.u_twitch.Twitch(*util_args)
        self.u_gacha = util.u_gacha.Gacha(*util_args)
        self.u_unscramblegame = util.u_unscramblegame.UnScrambleGame(*util_args)

        # ensure that any models needed methods from this instance can do so without circular import problems.
        models.base_util.ex = self
        # Dir that holds the generic models.
        self.u_objects: models = models

        # Util Directory that contains sql methods
        self.sql = s_sql

        # Modules/Cogs that contain 'ex' (Utility) and the 'conn' (DB connection).
        # AKA -> Classes that are have inherited IreneUtility.Base.Base()
        self.base_modules: List[Base.Base] = []

    def define_unique_properties(self, keys=None, events=None, weverse=False, data_dog=False, twitter=False,
                                 aiohttp=False, d_py_client=False, db_connection=False,
                                 base_modules: List[Base.Base] = None):
        """
        Define unique properties in Utility not defined in the constructor.

        :param self:
        :param keys: Access to the keys file.
        :param events: Access to the client-sided events class
        :param weverse: Whether to define weverse
        :param data_dog: Whether to initialize weverse
        :param twitter: Whether to define the twitter api
        :param aiohttp: Whether to define the aiohttp session.
        :param d_py_client: Whether to define the discord.py client.
        :param db_connection: Whether to define the db connection.
        :param base_modules: A list of instances that have the base modules with a parent containing ex and conn
        """
        if keys:
            self.keys = keys  # set the keys
        else:
            keys = self.keys  # have a fallback for no keys being passed in.

        if not keys:
            raise self.exceptions.NoKeyFound("No key access was found in Utility.define_unique_properties().")

        if base_modules:
            self.base_modules = base_modules

        if db_connection:
            self.u_database.set_start_up_connection.start()

        if data_dog:
            # only initialize datadog class after the keys have been set.
            self.u_data_dog.initialize_data_dog()  # initialize the class for DataDog metrics

        if d_py_client:
            # set discord client
            self.client = keys.client

        if aiohttp:
            # set aiohttp client session
            self.session = keys.client_session

        if weverse:
            # set weverse client
            self.weverse_client = WeverseClientAsync(authorization=keys.weverse_auth_token, web_session=self.session,
                                               verbose=True, loop=asyncio.get_event_loop())

        if twitter:
            # create twitter auth
            auth = tweepy.OAuthHandler(keys.CONSUMER_KEY, keys.CONSUMER_SECRET)
            auth.set_access_token(keys.ACCESS_KEY, keys.ACCESS_SECRET)
            self.api = tweepy.API(auth)

        if events:
            self.events = events

    async def get_user(self, user_id) -> models.User:
        """Creates a user if not created and adds it to the cache, then returns the user object.

        :rtype: models.User
        """
        user = self.cache.users.get(user_id)
        if not user:
            user = self.u_objects.User(user_id)
            self.cache.users[user_id] = user
        return user

    @staticmethod
    def first_result(record):
        """Returns the first item of a record if there is one."""
        if record:
            return record[0]

    @staticmethod
    def remove_commas(amount) -> int:
        """Remove all commas from a string and make it an integer."""
        try:
            balance = int(amount.replace(',', ''))
        except:
            balance = 0
        return balance

    @staticmethod
    def add_commas(amount: int) -> str:
        """Add commas to an integer and converts it to a string.

        :param amount: A value.
        :return: A string with the integer separated by commas.
        """
        return f"{amount:,}"

    async def kill_api(self):
        """restart the api"""
        source_link = "http://127.0.0.1:5123/restartAPI"
        async with self.session.get(source_link):
            log.console("Restarting API.", method=self.kill_api)

    @staticmethod
    async def get_server_id(ctx):
        """Get the server id by context or message."""
        # make sure ctx.guild exists in the case discord.py cache isn't loaded.
        if ctx.guild:
            return ctx.guild.id

    async def get_dm_channel(self, user_id=None, user=None):
        try:
            if user_id:
                # user = await self.client.fetch_user(user_id)
                user = self.client.get_user(user_id)
                if not user:
                    user = await self.client.fetch_user(user_id)
            dm_channel = user.dm_channel
            if not dm_channel:
                await user.create_dm()
                dm_channel = user.dm_channel
            return dm_channel
        except discord.errors.HTTPException as e:
            log.console(f"{e} (HTTPException)", method=self.get_dm_channel)
            return
        except AttributeError:
            return
        except Exception as e:
            log.console(f"{e} (Exception)", method=self.get_dm_channel)
            return

    async def check_interaction_enabled(self, ctx=None, server_id=None, interaction=None):
        """Check if the interaction is disabled in the current server, RETURNS False when it is disabled."""
        if not server_id and not interaction:
            server_id = await Utility.get_server_id(ctx)
            interaction = ctx.command.name
        interactions = await self.u_miscellaneous.get_disabled_server_interactions(server_id)
        if not interactions:
            return True
        interaction_list = interactions.split(',')
        if interaction in interaction_list:
            # normally we would alert the user that the command is disabled, but discord.py uses this function.
            return False
        return True

    def check_if_mod(self, ctx, mode=0):  # as mode = 1, ctx is the author id.
        """Check if the user is a bot mod/owner."""
        if not mode:
            user_id = ctx.author.id
            return user_id in self.keys.mods_list or user_id == self.keys.owner_id
        else:
            return ctx in self.keys.mods_list or ctx == self.keys.owner_id

    def get_ping(self):
        """Get the client's ping."""
        return int(self.client.latency * 1000)

    @staticmethod
    def get_random_color():
        """Retrieves a random hex color."""
        r = lambda: random.randint(0, 255)
        return int(('%02X%02X%02X' % (r(), r(), r())), 16)  # must be specified to base 16 since 0x is not present

    async def create_embed(self, title="Irene", color=None, title_desc=None, footer_desc="Thanks for using Irene!",
                           icon_url=None, footer_url=None):
        """Create a discord Embed."""
        icon_url = self.keys.icon_url if not icon_url else icon_url
        footer_url = self.keys.footer_url if not footer_url else footer_url
        color = self.get_random_color() if not color else color
        embed = discord.Embed(title=title, color=color) if not title_desc \
            else discord.Embed(title=title, color=color, description=title_desc)

        embed.set_author(name="Irene", url=self.keys.bot_website,
                         icon_url=icon_url)
        embed.set_footer(text=footer_desc, icon_url=footer_url)
        return embed

    async def wait_for_reaction(self, msg, user_id, reaction_needed):
        """Wait for a user's reaction on a message."""
        def react_check(reaction_used, user_reacted):
            return (user_reacted.id == user_id) and (reaction_used.emoji == reaction_needed)

        try:
            # noinspection PyUnusedLocal
            reaction, user = await self.client.wait_for('reaction_add', timeout=60, check=react_check)
            return True
        except asyncio.TimeoutError:
            await msg.delete()
            return False

    async def set_embed_author_and_footer(self, embed, footer_message):
        """Sets the author and footer of an embed."""
        embed.set_author(name="Irene", url=self.keys.bot_website,
                         icon_url='https://cdn.discordapp.com/emojis/693392862611767336.gif?v=1')
        embed.set_footer(text=footer_message,
                         icon_url='https://cdn.discordapp.com/emojis/683932986818822174.gif?v=1')
        return embed

    async def check_left_or_right_reaction_embed(self, msg, embed_lists, original_page_number=0, reaction1=None,
                                                 reaction2=None):
        """This method is used for going between pages of embeds."""
        reaction1 = self.keys.previous_emoji
        reaction2 = self.keys.next_emoji
        await msg.add_reaction(reaction1)  # left arrow by default
        await msg.add_reaction(reaction2)  # right arrow by default

        def reaction_check(user_reaction, reaction_user):
            """Check if the reaction is the right emoji and right user."""
            return ((user_reaction.emoji == '➡') or (
                        user_reaction.emoji == '⬅')) and reaction_user != msg.author and user_reaction.message.id == msg.id

        async def change_page(c_page):
            """Waits for the user's reaction and then changes the page based on their reaction."""
            try:
                reaction, user = await self.client.wait_for('reaction_add', check=reaction_check)
                if reaction.emoji == '➡':
                    c_page += 1
                    if c_page >= len(embed_lists):
                        c_page = 0  # start from the beginning of the list
                    await msg.edit(embed=embed_lists[c_page])

                elif reaction.emoji == '⬅':
                    c_page -= 1
                    if c_page < 0:
                        c_page = len(embed_lists) - 1  # going to the end of the list
                    await msg.edit(embed=embed_lists[c_page])

                # await msg.clear_reactions()
                # await msg.add_reaction(reaction1)
                # await msg.add_reaction(reaction2)
                # only remove user's reaction instead of all reactions
                try:
                    await reaction.remove(user)
                except:
                    pass
                await change_page(c_page)
            except Exception as e:
                log.console(f"{e} (Exception)", method=self.check_left_or_right_reaction_embed)
                await change_page(c_page)
        await change_page(original_page_number)

    async def get_server_prefix(self, id_ctx_message):
        """Gets the prefix of a server by the server ID, Context, or Message.

        :param id_ctx_message: Context, Message, or server id.
        :return: Server Prefix
        """
        try:
            if isinstance(id_ctx_message, Context) or isinstance(id_ctx_message, discord.Message):
                server_id = id_ctx_message.guild.id
            elif isinstance(id_ctx_message, int):
                server_id = id_ctx_message
            else:
                return self.keys.bot_prefix

            prefix = self.cache.server_prefixes.get(server_id) or self.keys.bot_prefix
            return prefix
        except:
            return self.keys.bot_prefix

    @staticmethod
    def check_file_exists(file_path):
        """Check if a file path exists."""
        return os.path.isfile(file_path)

    async def stop_game(self, ctx, games: dict):
        """Delete an ongoing game.

        :param ctx: Context object
        :param games: Dict of Games
        :return: False if no game was found
        """
        is_moderator = await self.u_miscellaneous.check_if_moderator(ctx)
        try:
            game = games.pop(ctx.channel.id)
        except KeyError:
            return False

        if game:
            if ctx.author.id == game.host_id or is_moderator:
                game.force_ended = True
                return await game.end_game()
            else:
                return await ctx.send("> You must be a moderator or the host of the game in order to end the game.")

    async def check_user_in_support_server(self, ctx):
        """Checks if a user is in the support server.
        If the support server is not in cache, it will count as if the user is in the server.
        d.py cache must be fully loaded before this is properly checked.
        """
        if not self.discord_cache_loaded:
            return True

        support_server = self.client.get_guild(self.keys.bot_support_server_id)
        if not support_server:
            return True
        if support_server.get_member(ctx.author.id):
            return True
        if ctx.author.id in self.cache.member_ids_in_support_server:
            return True

        user = await self.get_user(ctx.author.id)
        msg = await self.replace(self.cache.languages[user.language]['utility']['join_support_server_feature'],
                                 [['bot_name', self.keys.bot_name],
                                  ['support_server_link', self.keys.bot_support_server_link]])
        await ctx.send(msg)

    @staticmethod
    async def replace(text: str, inputs_to_change: list) -> str:
        """
        Replace custom text from language packs for several keywords at once.
        :param text: The text that requires replacing.
        :param inputs_to_change: A list of lists with the 0th index as the keyword to replace, and the 1st index
        as the content.
        :return: string with proper input.
        """
        # convert the input to a list of lists if it is not already.
        if not isinstance(inputs_to_change[0], list):
            inputs_to_change = [[inputs_to_change[0], inputs_to_change[1]]]

        # custom input is always surrounded by curly braces {} unless mentioning a user.
        for input_list in inputs_to_change:
            await asyncio.sleep(0)  # bare yield to not block main thread
            # make sure braces do not already exist in the input
            keyword = input_list[0]
            custom_input = str(input_list[1])

            keyword = keyword.replace("{", "")
            keyword = keyword.replace("}", "")
            text = text.replace("{" + keyword + "}", custom_input)

        return text

    async def get_msg(self, user, module, keyword, inputs_to_change: list = None) -> str:
        """Get a msg from a user's language.

        :param user: User ID, Irene User object, or Context object
        :param module: Module name (Case Sensitive)
        :param keyword: Key attached to the string
        :param inputs_to_change: Optional to change inputs with a nested list. ex: ["keyword", "input"]
        :return: message string from language pack.
        """

        # allow ctx as input to the user
        if isinstance(user, Context):
            user = user.author.id

        # allow user id as input to the user.
        if not isinstance(user, self.u_objects.User):
            user = await self.get_user(user)

        msg = self.cache.languages[user.language][module][keyword]

        if inputs_to_change:
            msg = await self.replace(msg, inputs_to_change)
        return msg

    async def run_blocking_code(self, func, *args):
        """Run blocking code safely in a new thread.

        :param func: The blocking function that needs to be called.
        :param args: The args to pass into the blocking function.
        :returns: result of asyncio.Future object
        """
        loop = asyncio.get_running_loop()
        try:
            with concurrent.futures.ThreadPoolExecutor() as pool:
                result = await loop.run_in_executor(pool, func, *args)
                log.console(f'Custom Thread Pool -> {func}', method=self.run_blocking_code, event_loop=self.client.
                            loop)
                return result if None else result.result()
        except AttributeError:
            return
        except Exception as e:
            log.console(f"{e} (Exception)", method=self.run_blocking_code, event_loop=self.client.loop)
