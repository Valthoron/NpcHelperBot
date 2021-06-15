import d20
import discord
import os
from discord.ext import commands
from dotenv import load_dotenv
from npchelper_dnd5e import NpcHelper_Dnd5e

load_dotenv()
DISCORD_ADMIN_ID = int(os.getenv("DISCORD_ADMIN_ID"))

class RollStringifier(d20.SimpleStringifier):
    def _str_expression(self, node):
        return f"{self._stringify(node.roll)}"


class Cog_NpcHelper_Dnd5e(commands.Cog, NpcHelper_Dnd5e):
    def __init__(self, bot):
        self.bot = bot
        NpcHelper_Dnd5e.__init__(self)

    @commands.command(name="npcdebug")
    async def debug(self, context, *command):
        if context.author.id != DISCORD_ADMIN_ID:
            return

        print("Channel = ", context.channel.id)
        print("Server = ", context.guild.id)

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
        action = command[0].lower()
        key = " ".join(command[1:])

        if character_name == "*":
            result, characters = self.find_all_characters(context.channel.id, context.guild.id)

            if result is False:
                await context.send("Error: No characters found in channel.")
                return

            for character_dict in characters:
                if "check".startswith(action):
                    await self.execute_check(context, character_dict, key)
                elif "save".startswith(action):
                    await self.execute_save(context, character_dict, key)
        else:
            result, character_dict = self.get_character(character_name, context.channel.id, context.guild.id)

            if result is False:
                await context.send("Error: Can't find character \"" + character_name + "\".")
                return

            if "check".startswith(action):
                await self.execute_check(context, character_dict, key)
            elif "save".startswith(action):
                await self.execute_save(context, character_dict, key)
            elif "attack".startswith(action):
                await self.execute_attack(context, character_dict, key)
            else:
                await context.send("Error: Unknown action \"" + action + "\".")
                return

        await context.message.delete()

    async def execute_check(self, context, character_dict, check):
        character_id = character_dict["id"]
        character_name = character_dict["name"]
        character_portrait = character_dict["portrait"]

        result, check_dict = self.get_check(character_id, check)

        if result is False:
            await context.send("Error: Can't find check \"" + check + "\" for character \"" + character_name + "\".")
            return

        check_name = check_dict["name"]
        check_modifier = check_dict["modifier"]

        dice = "1d20+" + str(check_modifier)
        roll = d20.roll(dice)

        embed = discord.Embed()
        embed.title = character_name + " makes a " + check_name + " check!"
        embed.description = str(roll)
        embed.color = 0x00ff00

        if character_portrait:
            embed.set_thumbnail(url=character_portrait)

        await context.send(embed=embed)

    async def execute_save(self, context, character_dict, save):
        character_id = character_dict["id"]
        character_name = character_dict["name"]
        character_portrait = character_dict["portrait"]

        result, save_dict = self.get_check(character_id, "save_" + save)

        if result is False:
            await context.send("Error: Can't find save \"" + save + "\" for character \"" + character_name + "\".")
            return

        save_name = save_dict["name"]
        save_modifier = save_dict["modifier"]

        dice = "1d20+" + str(save_modifier)
        roll = d20.roll(dice)

        embed = discord.Embed()
        embed.title = character_name + " makes a " + save_name + " save!"
        embed.description = str(roll)
        embed.color = 0x0000ff

        if character_portrait:
            embed.set_thumbnail(url=character_portrait)

        await context.send(embed=embed)

    async def execute_attack(self, context, character_dict, attack):
        character_id = character_dict["id"]
        character_name = character_dict["name"]
        character_portrait = character_dict["portrait"]

        result, attack_arr = self.get_attack(character_id, attack)

        if result is False:
            await context.send("Error: Can't find attack \"" + " ".join(attack_name) + "\" for character \"" + character_name + "\".")
            return

        embed_title = ""
        embed_description = ""

        if len(attack_arr) == 1:
            attack_dict = attack_arr[0]
            embed_title = character_name + " attacks with a " + attack_dict["name"] + "!"
            embed_description = await self.execute_attack_single(context, attack_dict)
        else:
            embed_title = character_name + " executes a multi-attack!"
            embed_description = ""
            for attack_dict in attack_arr:
                attack_description = await self.execute_attack_single(context, attack_dict)
                embed_description += attack_description + "\n"

        embed = discord.Embed()
        embed.title = embed_title
        embed.description = embed_description
        embed.color = 0xff0000

        if character_portrait:
            embed.set_thumbnail(url=character_portrait)

        await context.send(embed=embed)

    async def execute_attack_single(self, context, attack_dict):
        attack_name = attack_dict["name"]
        attack_hit = attack_dict["hit"]
        attack_damage = attack_dict["damage"]

        # Roll to hit
        hit_dice = "1d20+" + str(attack_hit)
        hit_roll = d20.roll(hit_dice)

        # Roll for damage
        damage_dice = attack_damage

        if hit_roll.crit == d20.dice.CritType.CRIT:
            # Double leftmost dice on a critical hit
            dice_parts = damage_dice.split("d", 1)
            dice_parts[0] = str(int(dice_parts[0])*2)
            damage_dice = "d".join(dice_parts)

        damage_roll = d20.roll(damage_dice)

        # Build attack text
        attack_text = "**" + attack_name + "**\n"
        attack_text += "**To Hit**: " + str(hit_roll) + "\n"

        if hit_roll.crit == d20.dice.CritType.CRIT:
            attack_text += "**Damage (CRIT!)**: " + str(damage_roll) + "\n"
        elif hit_roll.crit == d20.dice.CritType.FAIL:
            attack_text += "**Miss!**\n"
        else:
            attack_text += "**Damage**: " + str(damage_roll) + "\n"

        return attack_text

def setup(bot):
    bot.add_cog(Cog_NpcHelper_Dnd5e(bot))
