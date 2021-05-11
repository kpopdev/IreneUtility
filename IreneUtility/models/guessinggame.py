from . import Game as Game_Base
import asyncio
import random
import async_timeout
from IreneUtility.util import u_logger as log


# noinspection PyBroadException,PyPep8
class GuessingGame(Game_Base):
    def __init__(self, *args, max_rounds=20, timeout=20, gender="all", difficulty="medium"):
        """

        :param utility_obj: Utility object.
        :param ctx: Context
        :param max_rounds: The amount of rounds to stop at.
        :param timeout: Amount of time to guess a phoot.
        :param gender: Male/Female/All Gender of the idols in the photos.
        :param difficulty: Easy/Medium/Hard difficulty of the game.
        """
        super().__init__(*args)
        self.photo_link = None
        self.host_user = None  # Utility user object
        # user_id : score
        self.players = {}
        self.rounds = 0
        self.idol = None
        self.group_names = None
        self.correct_answers = []
        self.timeout = timeout
        self.max_rounds = max_rounds
        self.force_ended = False
        self.idol_post_msg = None
        self.gender = None
        self.post_attempt_timeout = 10
        if gender.lower() in self.ex.cache.male_aliases:
            self.gender = 'male'
        elif gender.lower() in self.ex.cache.female_aliases:
            self.gender = 'female'
        else:
            self.gender = "all"
        if difficulty in self.ex.cache.difficulty_selection.keys():
            self.difficulty = difficulty
        else:
            self.difficulty = "medium"

        self.idol_set: list = []
        self.results_posted = False
        self.api_issues = 0

    async def credit_user(self, user_id):
        """Increment a user's score"""
        score = self.players.get(user_id)
        if not score:
            self.players[user_id] = 1
        else:
            self.players[user_id] = score + 1
        self.rounds += 1

    async def check_message(self):
        """Check incoming messages in the text channel and determine if it is correct."""
        if self.force_ended:
            return

        stop_phrases = ['stop', 'end', 'quit']

        def check_correct_answer(message):
            """Check if the user has the correct answer."""
            if message.channel != self.channel:
                return False
            if message.content.lower() in self.correct_answers:
                return True
            if message.author.id == self.host_id:
                return message.content.lower() == 'skip' or message.content.lower() in stop_phrases

        try:
            msg = await self.ex.client.wait_for('message', check=check_correct_answer, timeout=self.timeout)
            await msg.add_reaction(self.ex.keys.check_emoji)
            if msg.content.lower() == 'skip':
                await self.print_answer(question_skipped=True)
                return
            elif msg.content.lower() in self.correct_answers:
                await self.credit_user(msg.author.id)
            elif msg.content.lower() in stop_phrases or self.force_ended:
                self.force_ended = True
                return
            else:
                # the only time this code is reached is when a prefix was changed in the middle of a round.
                # for example, if the user had to guess "irene", but their server prefix was 'i', then
                # the bot will change the msg content to "%rene" and the above conditions will not properly work.
                # if we had reached this point, we'll give them +1 instead of ending the game
                await self.credit_user(msg.author.id)

        except asyncio.TimeoutError:
            if not self.force_ended:
                await self.print_answer()
                self.rounds += 1

    async def create_new_question(self):
        """Create a new question and send it to the channel."""
        # noinspection PyBroadException
        question_posted = False
        while not question_posted:
            try:
                if self.idol_post_msg:
                    try:
                        await self.idol_post_msg.delete()
                    except Exception as e:
                        # message does not exist.
                        log.useless(f"{e} - Likely message doesn't exist - GuessingGame.Game.create_new_question")

                # Create random idol selection
                if not self.idol_set:
                    raise LookupError(f"No valid idols for the group {self.gender} and {self.difficulty}.")
                self.idol = random.choice(self.idol_set)

                # Create acceptable answers
                await self.create_acceptable_answers()

                # Create list of idol group names.
                self.group_names = [(await self.ex.u_group_members.get_group(group_id)).name
                                    for group_id in self.idol.groups]

                # Skip this idol if it is taking too long
                async with async_timeout.timeout(self.post_attempt_timeout) as posting:
                    self.idol_post_msg, self.photo_link = await self.ex.u_group_members.idol_post(
                        self.channel, self.idol, user_id=self.host_id, guessing_game=True, scores=self.players)
                    log.console(f'{", ".join(self.correct_answers)} - {self.channel.id}')

                if posting.expired:
                    log.console(f"Posting for {self.idol.full_name} ({self.idol.stage_name}) [{self.idol.id}]"
                                f" took more than {self.post_attempt_timeout}")
                    continue
                question_posted = True
            except LookupError:
                raise
            except Exception as e:
                log.console(e)
                continue

    async def display_winners(self):
        """Displays the winners and their scores."""
        final_scores = ""
        if self.players:
            for user_id in self.players:
                final_scores += f"<@{user_id}> -> {self.players.get(user_id)}\n"
        return await self.channel.send(f">>> Guessing game has finished.\nScores:\n{final_scores}")

    async def end_game(self):
        """Ends a guessing game."""
        if self.results_posted:
            return True

        self.force_ended = True
        self.rounds = self.max_rounds
        if not self.host_user.gg_filter:
            # only update scores when there is no group filter on.
            await self.update_scores()
        await self.display_winners()
        self.results_posted = True
        return True

    async def update_scores(self):
        """Updates all player scores"""
        for user_id in self.players:
            await self.ex.u_guessinggame.update_user_guessing_game_score(self.difficulty, user_id=user_id,
                                                                         score=self.players.get(user_id))

    async def print_answer(self, question_skipped=False):
        """Prints the current round's answer."""
        skipped = ""
        if question_skipped:
            skipped = "Question Skipped. "
        msg = await self.channel.send(f"{skipped}The correct answer was "
                                      f"`{self.idol.full_name} ({self.idol.stage_name})`"
                                      f" from the following group(s): `{', '.join(self.group_names)}`", delete_after=15)
        # create_task should not be awaited because this is meant to run in the background to check for reactions.
        try:
            # noinspection PyUnusedLocal
            # create task to check image reactions.
            asyncio.create_task(self.ex.u_group_members.check_idol_post_reactions(
                msg, self.host_ctx.message, self.idol, self.photo_link, guessing_game=True))
        except Exception as e:
            log.console(e)

    async def create_acceptable_answers(self):
        """Create acceptable answers."""
        self.correct_answers = [alias.lower() for alias in self.idol.aliases]
        self.correct_answers.append(self.idol.full_name.lower())
        self.correct_answers.append(self.idol.stage_name.lower())

    async def create_idol_pool(self):
        """Create the game's idol pool."""
        idol_gender_set = self.ex.cache.gender_selection.get(self.gender)
        idol_difficulty_set = self.ex.cache.difficulty_selection.get(self.difficulty)
        idol_filtered_set = set()
        self.ex.cache.idols_female.update({idol for idol in self.ex.cache.idols if idol.gender == 'f'
                                           and idol.photo_count})
        if self.host_user.gg_filter:
            for group in self.host_user.gg_groups:
                idol_filtered_set.update(
                    {await self.ex.u_group_members.get_member(idol_id) for idol_id in group.members})
            self.idol_set = list(idol_gender_set & idol_difficulty_set & idol_filtered_set)
        else:
            self.idol_set = list(idol_gender_set & idol_difficulty_set)

    async def process_game(self):
        """Ignores errors and continuously makes new questions until the game should end."""
        self.host_user = await self.ex.get_user(self.host_id)
        await self.create_idol_pool()
        try:
            while self.rounds < self.max_rounds and not self.force_ended:
                try:
                    await self.create_new_question()
                except LookupError as e:
                    await self.channel.send(f"The gender, difficulty, and filtered settings selected have no idols. "
                                            f"Ending Game.")
                    log.console(e)
                    return
                await self.check_message()
            await self.end_game()
        except Exception as e:
            await self.channel.send(f"An error has occurred and the game has ended. Please report this.")
            log.console(e)