import d20
import discord
import os
from discord.ext import commands
from dotenv import load_dotenv
from npchelper_dnd5e import NpcHelper_Dnd5e

load_dotenv()
DISCORD_ADMIN_ID = int(os.getenv("DISCORD_ADMIN_ID"))
KEYWORD_LIST = ["adv", "dis"]

def parse_arguments(args):
    last_argument_index = len(args)

    # Filter switches
    switches = {}

    if len(args) > 2:
        for i in range(last_argument_index-1, 0, -2):
            if args[i-1].startswith("-"):
                last_argument_index = i - 1
                switch = args[i-1][1:].lower()
                value = args[i].lower()
                switches[switch] = value

    # Filter keywords
    keywords = []

    if len(args) > 1:
        for i in range(last_argument_index-1, 0, -1):
            if args[i].lower() in KEYWORD_LIST:
                last_argument_index = i
                keyword = args[i].lower()
                keywords.append(keyword)
            else:
                break

    # Return remaining args
    filtered_args = args[:last_argument_index]
    return filtered_args, keywords, switches

class Cog_NpcHelper_Dnd5e(commands.Cog, NpcHelper_Dnd5e):
    def __init__(self, bot):
        self.bot = bot
        NpcHelper_Dnd5e.__init__(self)

    @commands.command(name="npcdebug")
    async def debug(self, context, *command):
        if context.author.id != DISCORD_ADMIN_ID:
            return

        await context.send("Channel = " + str(context.channel.id) + "\nServer = " + str(context.guild.id))

    @commands.command(name="npclist")
    async def list(self, context):
        result, characters = self.find_all_characters(context.channel.id, context.guild.id)

        if result:
            response = "Characters in this channel:"
            for character in characters:
                response += "\n" + character["name"]
        else:
            response = "No characters found in channel."

        await context.send(response)

    @commands.command(name="npcadd")
    async def add(self, context, url):
        result, character = self.add_character(url, context.channel.id, context.guild.id)

        if result is False:
            await context.send("Error: Can't add character.")
            return

        await context.send("Added \"" + character["name"] + "\" to channel.")

    @commands.command(name="npcremove")
    async def remove(self, context, name):
        result, character_dict = self.get_character(name, context.channel.id, context.guild.id)

        if result is False:
            await context.send("Error: Can't find character \"" + name + "\".")
            return

        character_id = character_dict["id"]
        character_name = character_dict["name"]

        self.remove_character(character_id)

        await context.send("Character \"" + character_name + "\" removed from channel.")

    @commands.command(name="npcupdate")
    async def update(self, context, name):
        result, character_dict = self.get_character(name, context.channel.id, context.guild.id)

        if result is False:
            await context.send("Error: Can't find character \"" + name + "\".")
            return

        character_id = character_dict["id"]
        character_name = character_dict["name"]

        message = await context.send("Updating \"" + character_name + "\"...")

        self.update_character_by_id(character_id)

        await message.edit(content="Updated \"" + character_name + "\".")

    @commands.command(name="npc")
    async def action(self, context, character_name, *command):
        if len(command) < 1:
            return

        command_args, command_keywords, command_switches = parse_arguments(command)

        action = command_args[0].lower()
        key = " ".join(command_args[1:])

        if character_name == "*":
            result, characters = self.find_all_characters(context.channel.id, context.guild.id)

            if result is False:
                await context.send("Error: No characters found in channel.")
                return

            for character_dict in characters:
                if "check".startswith(action):
                    await self.execute_check(context, character_dict, key, command_keywords, command_switches)
                elif "save".startswith(action):
                    await self.execute_save(context, character_dict, key, command_keywords, command_switches)
                elif "initiative".startswith(action):
                    await self.execute_initiative(context, character_dict, key, command_keywords, command_switches)
                else:
                    await context.send("Error: Unknown action \"" + action + "\".")
                    return
        else:
            result, character_dict = self.get_character(character_name, context.channel.id, context.guild.id)

            if result is False:
                await context.send("Error: Can't find character \"" + character_name + "\".")
                return

            if "check".startswith(action):
                result = await self.execute_check(context, character_dict, key, command_keywords, command_switches)
            elif "save".startswith(action):
                result = await self.execute_save(context, character_dict, key, command_keywords, command_switches)
            elif "attack".startswith(action):
                result = await self.execute_attack(context, character_dict, key, command_keywords, command_switches)
            elif "initiative".startswith(action):
                result = await self.execute_initiative(context, character_dict, key, command_keywords, command_switches)
            else:
                await context.send("Error: Unknown action \"" + action + "\".")
                return

            if result is False:
                return

        await context.message.delete()

    async def execute_check(self, context, character_dict, check, keywords=[], switches={}):
        character_id = character_dict["id"]
        character_name = character_dict["name"]
        character_portrait = character_dict["portrait"]

        result, check_dict = self.get_check(character_id, check)

        if result is False:
            await context.send("Error: Can't find check \"" + check + "\" for character \"" + character_name + "\".")
            return False

        check_name = check_dict["name"]
        check_modifier = check_dict["modifier"]

        if "adv" in keywords:
            dice = "2d20kh1"
        elif "dis" in keywords:
            dice = "2d20kl1"
        else:
            dice = "1d20"

        dice += "+" + str(check_modifier)
        roll = d20.roll(dice)

        embed = discord.Embed()
        embed.title = character_name + " makes a " + check_name + " check!"
        embed.description = str(roll)
        embed.color = 0x00ff00

        if character_portrait:
            embed.set_thumbnail(url=character_portrait)

        if "adv" in keywords:
            embed.description = "`Advantage`\n" + embed.description
        elif "dis" in keywords:
            embed.description = "`Disadvantage`\n" + embed.description

        sent_message: discord.Message = await context.send(embed=embed)

        if roll.crit == d20.dice.CritType.CRIT:
            await sent_message.add_reaction("\U00002764")
        elif roll.crit == d20.dice.CritType.FAIL:
            await sent_message.add_reaction("\U0001F622")

        return True

    async def execute_save(self, context, character_dict, save, keywords=[], switches={}):
        character_id = character_dict["id"]
        character_name = character_dict["name"]
        character_portrait = character_dict["portrait"]

        result, save_dict = self.get_check(character_id, "save_" + save)

        if result is False:
            await context.send("Error: Can't find save \"" + save + "\" for character \"" + character_name + "\".")
            return False

        save_name = save_dict["name"]
        save_modifier = save_dict["modifier"]

        if "adv" in keywords:
            dice = "2d20kh1"
        elif "dis" in keywords:
            dice = "2d20kl1"
        else:
            dice = "1d20"

        dice += "+" + str(save_modifier)
        roll = d20.roll(dice)

        embed = discord.Embed()
        embed.title = character_name + " makes a " + save_name + " save!"
        embed.description = str(roll)
        embed.color = 0x0000ff

        if character_portrait:
            embed.set_thumbnail(url=character_portrait)

        if "adv" in keywords:
            embed.description = "`Advantage`\n" + embed.description
        elif "dis" in keywords:
            embed.description = "`Disadvantage`\n" + embed.description

        sent_message: discord.Message = await context.send(embed=embed)

        if roll.crit == d20.dice.CritType.CRIT:
            await sent_message.add_reaction("\U00002764")
        elif roll.crit == d20.dice.CritType.FAIL:
            await sent_message.add_reaction("\U0001F622")

        return True

    async def execute_initiative(self, context, character_dict, save, keywords=[], switches={}):
        character_id = character_dict["id"]
        character_name = character_dict["name"]
        character_portrait = character_dict["portrait"]

        _, check_dict = self.get_check(character_id, "bonus_initiative")

        check_modifier = check_dict["modifier"]

        if "adv" in keywords:
            dice = "2d20kh1"
        elif "dis" in keywords:
            dice = "2d20kl1"
        else:
            dice = "1d20"

        dice += "+" + str(check_modifier)
        roll = d20.roll(dice)

        embed = discord.Embed()
        embed.title = character_name + " rolls for initiative!"
        embed.description = str(roll)
        embed.color = 0xff8800

        if character_portrait:
            embed.set_thumbnail(url=character_portrait)

        if "adv" in keywords:
            embed.description = "`Advantage`\n" + embed.description
        elif "dis" in keywords:
            embed.description = "`Disadvantage`\n" + embed.description

        await context.send(embed=embed)

        return True

    async def execute_attack(self, context: commands.Context, character_dict, attack, keywords=[], switches={}):
        character_id = character_dict["id"]
        character_name = character_dict["name"]
        character_portrait = character_dict["portrait"]

        result, attack_arr = self.get_attack(character_id, attack)

        if result is False:
            await context.send("Error: Can't find attack \"" + attack + "\" for character \"" + character_name + "\".")
            return False

        embed_title = ""
        embed_description = ""

        critical_hit = False
        critical_miss = False

        if len(attack_arr) == 1:
            attack_dict = attack_arr[0]
            embed_title = character_name + " attacks with a " + attack_dict["name"] + "!"
            embed_description, critical_hit, critical_miss = await self.execute_attack_single(character_dict, attack_dict, keywords=keywords, switches=switches)
        else:
            embed_title = character_name + " executes a multi-attack!"
            embed_description = ""
            critical_hit = False
            critical_miss = False

            for attack_dict in attack_arr:
                attack_description, critical_hit_one, critical_miss_one = await self.execute_attack_single(character_dict, attack_dict, include_name=True, keywords=keywords, switches=switches)
                embed_description += attack_description + "\n"
                critical_hit |= critical_hit_one
                critical_miss |= critical_miss_one

        embed = discord.Embed()
        embed.title = embed_title
        embed.description = embed_description
        embed.color = 0xff0000

        if character_portrait:
            embed.set_thumbnail(url=character_portrait)

        if "adv" in keywords:
            embed.description = "`Advantage`\n" + embed.description
        elif "dis" in keywords:
            embed.description = "`Disadvantage`\n" + embed.description

        sent_message: discord.Message = await context.send(embed=embed)

        if critical_hit:
            await sent_message.add_reaction("\U00002764")
        
        if critical_miss:
            await sent_message.add_reaction("\U0001F622")

        return True

    async def execute_attack_single(self, character_dict, attack_dict, include_name=False, keywords=[], switches={}):
        character_system = character_dict["system"]

        if character_system == "dnd5":
            return self.execute_attack_single_5e(character_dict, attack_dict, include_name, keywords, switches)
        
        return self.execute_attack_single_35e(character_dict, attack_dict, include_name, keywords, switches)
    
    def execute_attack_single_5e(self, character_dict, attack_dict, include_name=False, keywords=[], switches={}):
        attack_name = attack_dict["name"]
        attack_hit = attack_dict["hit"]
        attack_damage = attack_dict["damage"]

        # Roll to hit
        if "adv" in keywords:
            hit_dice = "2d20kh1"
        elif "dis" in keywords:
            hit_dice = "2d20kl1"
        else:
            hit_dice = "1d20"

        hit_dice += "+" + str(attack_hit)
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
        damage_dice = attack_damage

        if critical_hit:
            # Double leftmost dice
            dice_parts = damage_dice.split("d", 1)
            dice_parts[0] = str(int(dice_parts[0])*2)
            damage_dice = "d".join(dice_parts)

        damage_roll = d20.roll(damage_dice)

        # Build attack text
        attack_text = ""

        if include_name:
            attack_text += "**" + attack_name + "**\n"

        attack_text += "**To Hit**: " + str(hit_roll) + "\n"

        if critical_hit:
            attack_text += "**Damage (CRIT!)**: " + str(damage_roll) + "\n"
        elif critical_miss:
            attack_text += "**Miss!**\n"
        else:
            attack_text += "**Damage**: " + str(damage_roll) + "\n"

        return attack_text, critical_hit, critical_miss

    def execute_attack_single_35e(self, character_dict, attack_dict, include_name=False, keywords=[], switches={}):
        attack_name = attack_dict["name"]
        attack_hit = attack_dict["hit"]
        attack_damage = attack_dict["damage"]
        attack_critrange = attack_dict["critrange"]
        attack_critmultiplier = attack_dict["critmultiplier"]

        # Roll to hit
        hit_dice = "1d20+" + str(attack_hit)
        hit_roll = d20.roll(hit_dice)

        # Check for critical hit
        critical_hit = False
        critical_miss = False
        confirm_roll = None

        # Critical if roll is above threat threshold, also confirm
        d20_value = d20.utils.leftmost(hit_roll.expr).total
        if d20_value >= int(attack_critrange):
            critical_hit = True
            confirm_roll = d20.roll(hit_dice)
        elif d20_value == 1:
            critical_miss = True
            confirm_roll = d20.roll(hit_dice)

        # Roll for damage
        damage_dice = attack_damage

        damage_roll = d20.roll(damage_dice)

        # Build attack text
        attack_text = ""

        if include_name:
            attack_text += "**" + attack_name + "**\n"

        attack_text += "**To Hit**: " + str(hit_roll) + "\n"

        if critical_hit:
            attack_text += "**Critical Hit!**\n"
        elif critical_miss:
            attack_text += "**Critical Miss!**\n"

        if critical_hit or critical_miss:
            attack_text += "**Confirm**: " + str(confirm_roll) + "\n"

        if not critical_miss:
            attack_text += "**Damage**: " + str(damage_roll) + "\n"

        if critical_hit:
            attack_text += "**Critical Damage**: `" + str(damage_roll.total * int(attack_critmultiplier)) + "`\n"

        return attack_text, critical_hit, critical_miss

def setup(bot):
    bot.add_cog(Cog_NpcHelper_Dnd5e(bot))
