import os

import d20
import discord

from discord.ext import commands
from discord.message import Message
from dotenv import load_dotenv
from pymongo.collection import Collection
from pymongo.database import Database

from character import Character

load_dotenv()
DISCORD_ADMIN_ID = int(os.getenv("DISCORD_ADMIN_ID"))
KEYWORD_LIST = ["adv", "dis"]


def parse_arguments(args):
    last_argument_index = len(args)

    # Filter switches
    switches = {}

    if len(args) > 2:
        for i in range(last_argument_index - 1, 0, -2):
            if args[i - 1].startswith("-"):
                last_argument_index = i - 1
                switch = args[i - 1][1:].lower()
                value = args[i].lower()
                switches[switch] = value

    # Filter keywords
    keywords = []

    if len(args) > 1:
        for i in range(last_argument_index - 1, 0, -1):
            if args[i].lower() in KEYWORD_LIST:
                last_argument_index = i
                keyword = args[i].lower()
                keywords.append(keyword)
            else:
                break

    # Return remaining args
    filtered_args = args[:last_argument_index]
    return filtered_args, keywords, switches


def parse_advantage(keywords: list) -> int:
    if "adv" in keywords and "dis" not in keywords:
        return 1

    if "dis" in keywords and "adv" not in keywords:
        return -1

    return 0


def get_article(noun: str) -> str:
    noun = noun.lower()

    if noun.startswith("the"):
        return ""

    if noun[0] in ["a", "e", "i", "o", "u"]:
        return "an"

    return "a"


def with_article(noun: str) -> str:
    return f"{get_article(noun)} {noun}"


class Cog_NpcHelper_Dnd5e(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.mdb: Database = bot.mdb
        self.characters: Collection = self.mdb.characters

    @commands.command(name="npclist")
    async def list(self, context: commands.Context):
        character_list = await Character.get_all(self.characters, context.channel.id)

        if len(character_list) == 0:
            await context.send("No characters found in channel.")
            return

        response = "Characters in this channel:\n"
        response += "\n".join([f"\u2022 {character.name}" for character in character_list])
        await context.send(response)

    @commands.command(name="npcadd")
    async def add(self, context: commands.Context, url: str):
        character = Character.create(self.characters, context.channel.id, url)
        character.update()
        await character.commit()
        await context.send(f"Added {character.name} to channel.")

    @commands.command(name="npcremove")
    async def remove(self, context: commands.Context, *, name):
        print(name)

        character = await Character.get(self.characters, context.channel.id, name, exact=True)

        if character is None:
            await context.send(f"Error: Can't find character \"{name}\". Please make sure to type the exact name of the character, including capitalization.")
            return

        await character.delete()
        await context.send(f"{character.name} removed from channel.")

    @commands.command(name="npcupdate")
    async def update(self, context: commands.Context, name: str):
        character = await Character.get(self.characters, context.channel.id, name)

        if character is None:
            await context.send(f"Error: Can't find character \"{name}\".")
            return

        message: Message = await context.send(f"Updating {character.name}...")
        character.update()
        await character.commit()
        await message.edit(content=f"Updated {character.name}.")

    @commands.command(name="npc")
    async def action(self, context, character_name, *command):
        if len(command) < 1:
            return

        command_args, command_keywords, command_switches = parse_arguments(command)

        action = command_args[0].lower()
        key = " ".join(command_args[1:])

        if character_name == "*":
            character_list = await Character.get_all(self.characters, context.channel.id)

            if len(character_list) == 0:
                await context.send("No characters found in channel.")
                return

            for character in character_list:
                if "check".startswith(action):
                    await self.execute_check(context, character, key, command_keywords, command_switches)
                elif "save".startswith(action):
                    await self.execute_save(context, character, key, command_keywords, command_switches)
                elif "initiative".startswith(action):
                    await self.execute_initiative(context, character, command_keywords, command_switches)
                else:
                    await context.send("Error: Unknown action \"" + action + "\".")
                    return
        else:
            character = await Character.get(self.characters, context.channel.id, character_name)

            if character is None:
                await context.send("Error: Can't find character \"" + character_name + "\".")
                return

            if "check".startswith(action):
                result = await self.execute_check(context, character, key, command_keywords, command_switches)
            elif "save".startswith(action):
                result = await self.execute_save(context, character, key, command_keywords, command_switches)
            elif "attack".startswith(action):
                result = await self.execute_attack(context, character, key, command_keywords, command_switches)
            elif "initiative".startswith(action):
                result = await self.execute_initiative(context, character, command_keywords, command_switches)
            else:
                await context.send("Error: Unknown action \"" + action + "\".")
                return

            if result is False:
                return

        await context.message.delete()

    async def execute_check(self, context, character: Character, check_name: str, keywords=[], switches={}):
        check = character.get_ability(check_name)

        if check is None:
            check = character.get_skill(check_name)

        if check is None:
            await context.send(f"Error: Can't find check \"{check_name}\" for {character.name}.")
            return False

        keywords.extend(check["keywords"])

        advantage = parse_advantage(keywords)
        if advantage > 0:
            dice = "2d20kh1"
        elif advantage < 0:
            dice = "2d20kl1"
        else:
            dice = "1d20"

        dice += "+" + str(check["modifier"])
        roll = d20.roll(dice)

        embed = discord.Embed()
        embed.title = f"{character.name} makes {with_article(check['name'])} check!"
        embed.description = str(roll)
        embed.color = 0x00ff00

        if character.portrait:
            embed.set_thumbnail(url=character.portrait)

        if advantage > 0:
            embed.description = "`Advantage`\n" + embed.description
        elif advantage < 0:
            embed.description = "`Disadvantage`\n" + embed.description

        sent_message: discord.Message = await context.send(embed=embed)

        if roll.crit == d20.dice.CritType.CRIT:
            await sent_message.add_reaction("\U00002764")
        elif roll.crit == d20.dice.CritType.FAIL:
            await sent_message.add_reaction("\U0001F622")

        return True

    async def execute_save(self, context, character: Character, save_name: str, keywords=[], switches={}):
        save = character.get_save(save_name)

        if save is None:
            await context.send(f"Error: Can't find save \"{save_name}\" for {character.name}.")
            return False

        keywords.extend(save["keywords"])

        advantage = parse_advantage(keywords)
        if advantage > 0:
            dice = "2d20kh1"
        elif advantage < 0:
            dice = "2d20kl1"
        else:
            dice = "1d20"

        dice += "+" + str(save["modifier"])
        roll = d20.roll(dice)

        embed = discord.Embed()
        embed.title = f"{character.name} makes {with_article(save['name'])} save!"
        embed.description = str(roll)
        embed.color = 0x0000ff

        if character.portrait:
            embed.set_thumbnail(url=character.portrait)

        if advantage > 0:
            embed.description = "`Advantage`\n" + embed.description
        elif advantage < 0:
            embed.description = "`Disadvantage`\n" + embed.description

        sent_message: discord.Message = await context.send(embed=embed)

        if roll.crit == d20.dice.CritType.CRIT:
            await sent_message.add_reaction("\U00002764")
        elif roll.crit == d20.dice.CritType.FAIL:
            await sent_message.add_reaction("\U0001F622")

        return True

    async def execute_initiative(self, context, character: Character, keywords=[], switches={}):
        keywords.extend(character.initiative["keywords"])

        advantage = parse_advantage(keywords)
        if advantage > 0:
            dice = "2d20kh1"
        elif advantage < 0:
            dice = "2d20kl1"
        else:
            dice = "1d20"

        dice += "+" + str(character.initiative["modifier"])
        roll = d20.roll(dice)

        embed = discord.Embed()
        embed.title = f"{character.name} rolls for initiative!"
        embed.description = str(roll)
        embed.color = 0xff8800

        if character.portrait:
            embed.set_thumbnail(url=character.portrait)

        if advantage > 0:
            embed.description = "`Advantage`\n" + embed.description
        elif advantage < 0:
            embed.description = "`Disadvantage`\n" + embed.description

        await context.send(embed=embed)

        return True

    async def execute_attack(self, context: commands.Context, character: Character, attack_name, keywords=[], switches={}):
        attack_list = character.get_attacks(attack_name)

        if attack_list is None:
            await context.send(f"Error: Can't find attack \"{attack_name}\" for {character.name}.")
            return False

        embed_title = ""
        embed_description = ""

        critical_hit = False
        critical_miss = False

        if len(attack_list) == 1:
            attack = attack_list[0]
            embed_title = f"{character.name} attacks with {with_article(attack['name'])}!"
            embed_description, critical_hit, critical_miss = await self.execute_attack_single(character, attack, keywords=keywords, switches=switches)
        else:
            embed_title = f"{character.name} executes a multi-attack!"
            embed_description = ""
            critical_hit = False
            critical_miss = False

            for attack in attack_list:
                attack_description, critical_hit_one, critical_miss_one = await self.execute_attack_single(character, attack, include_name=True, keywords=keywords, switches=switches)
                embed_description += attack_description + "\n"
                critical_hit |= critical_hit_one
                critical_miss |= critical_miss_one

        embed = discord.Embed()
        embed.title = embed_title
        embed.description = embed_description
        embed.color = 0xff0000

        if character.portrait:
            embed.set_thumbnail(url=character.portrait)

        advantage = parse_advantage(keywords)
        if advantage > 0:
            embed.description = "`Advantage`\n" + embed.description
        elif advantage < 0:
            embed.description = "`Disadvantage`\n" + embed.description

        sent_message: discord.Message = await context.send(embed=embed)

        if critical_hit:
            await sent_message.add_reaction("\U00002764")

        if critical_miss:
            await sent_message.add_reaction("\U0001F622")

        return True

    async def execute_attack_single(self, character: Character, attack, include_name=False, keywords=[], switches={}):
        keywords.extend(attack["keywords"])

        if character.system == "dnd5":
            return self.execute_attack_single_5e(character, attack, include_name, keywords, switches)

        return self.execute_attack_single_35e(character, attack, include_name, keywords, switches)

    def execute_attack_single_5e(self, character: Character, attack, include_name=False, keywords=[], switches={}):
        # Roll to hit
        advantage = parse_advantage(keywords)
        if advantage > 0:
            hit_dice = "2d20kh1"
        elif advantage < 0:
            hit_dice = "2d20kl1"
        else:
            hit_dice = "1d20"

        hit_dice += "+" + str(attack["hit"])
        hit_roll = d20.roll(hit_dice)

        # Check for critical hit
        critical_hit = False
        critical_miss = False

        # Critical on a natural 20
        if hit_roll.crit == d20.dice.CritType.CRIT:
            critical_hit = True
        elif hit_roll.crit == d20.dice.CritType.FAIL:
            critical_miss = True

        # Roll for damage
        damage_dice = attack["damage"]

        if critical_hit:
            # Double leftmost dice
            dice_parts = damage_dice.split("d", 1)
            dice_parts[0] = str(int(dice_parts[0]) * 2)
            damage_dice = "d".join(dice_parts)

        damage_roll = d20.roll(damage_dice)

        # Build attack text
        attack_text = ""

        if include_name:
            attack_text += f"**{attack['name']}**\n"

        attack_text += f"**To Hit**: {str(hit_roll)}\n"

        if critical_hit:
            attack_text += f"**Damage (CRIT!)**: {str(damage_roll)}\n"
        elif critical_miss:
            attack_text += "**Miss!**\n"
        else:
            attack_text += f"**Damage**: {str(damage_roll)}\n"

        return attack_text, critical_hit, critical_miss

    def execute_attack_single_35e(self, character: Character, attack, include_name=False, keywords=[], switches={}):
        bonus_attack = 0
        bonus_damage = 0
        extra_text = []

        if "pow" in switches:
            # Power attack
            power_attack_points = max(int(switches["pow"]), 0)
            power_attack_attack = -1 * power_attack_points
            power_attack_damage = (power_attack_points * 2) if "2h" in keywords else (power_attack_points)
            extra_text.append(f"_Power Attack: {power_attack_attack} to hit, +{power_attack_damage} to damage_")
            bonus_attack += power_attack_attack
            bonus_damage += power_attack_damage

        # Roll to hit
        hit_dice = f"1d20+{attack['hit']}"

        if bonus_attack != 0:
            hit_dice += f"+{bonus_attack}"

        hit_roll = d20.roll(hit_dice)

        # Check for critical hit
        critical_hit = False
        critical_miss = False
        confirm_roll = None

        # Critical if roll is above threat threshold, also confirm
        d20_value = d20.utils.leftmost(hit_roll.expr).total
        if d20_value >= attack["critrange"]:
            critical_hit = True
            confirm_roll = d20.roll(hit_dice)
        elif d20_value == 1:
            critical_miss = True
            confirm_roll = d20.roll(hit_dice)

        # Roll for damage
        damage_dice = attack["damage"]

        if bonus_damage != 0:
            damage_dice += f"+{bonus_damage}"

        damage_roll = d20.roll(damage_dice)

        # Build attack text
        attack_text = ""

        if include_name:
            attack_text += f"**{attack['name']}**\n"

        attack_text += "**To Hit**: " + str(hit_roll) + "\n"

        if critical_hit:
            attack_text += "**Critical Hit!**\n"
        elif critical_miss:
            attack_text += "**Critical Miss!**\n"

        if critical_hit or critical_miss:
            attack_text += f"**Confirm**: {str(confirm_roll)}\n"

        if not critical_miss:
            attack_text += f"**Damage**: {str(damage_roll)}\n"

        if critical_hit:
            damage_critical = damage_roll.total * attack["critmultiplier"]
            attack_text += f"**Critical Damage**: `{str(damage_critical)}`\n"

        for extra in extra_text:
            attack_text += f"\n{extra}"

        return attack_text, critical_hit, critical_miss


def setup(bot):
    bot.add_cog(Cog_NpcHelper_Dnd5e(bot))
