from __future__ import annotations

import re

import gspread

from pymongo.collection import Collection

from google_sheet import GoogleSheet


def parse_advantage(cells: list, column: int, block: list):
    if len(cells) > column:
        advantage = int(cells[column])
        if advantage > 0:
            block.append("adv")
        elif advantage < 0:
            block.append("dis")


def parse_optional_int(cells: list, column: int, default: int):
    if len(cells) > column:
        if cells[column] != "":
            return int(cells[column])

    return default


class Character:
    def __init__(self):
        self._id = None
        self._collection: Collection = None
        self.channel: int = -1
        self.sheet = ""
        self.system = ""
        self.name = ""
        self.portrait = ""
        self.initiative = {}
        self.abilities = []
        self.saves = []
        self.skills = []
        self.attacks = []

    def update(self, sheet_url: str = None):
        if sheet_url is not None:
            self.sheet = gspread.utils.extract_id_from_url(sheet_url)

        sheet = GoogleSheet.get_service().open_by_key(self.sheet).get_worksheet(0)

        # Parse character sheet
        system = sheet.get("system").first()
        name = sheet.get("name").first()
        portrait = sheet.get("portrait").first()
        initiative = sheet.get("initiative")[0]
        abilities = sheet.get("Abilities")
        saves = sheet.get("Saves")
        skills = sheet.get("Skills")
        attacks = sheet.get("Attacks")

        # Fill in character object
        self.system = system
        self.name = name
        self.portrait = portrait

        self.initiative = {}
        self.initiative["modifier"] = int(initiative[0])
        self.initiative["keywords"] = []
        parse_advantage(initiative, 1, self.initiative["keywords"])

        self.abilities = []
        self.saves = []
        self.skills = []
        self.attacks = []

        for ability in abilities:
            new_ability = {}
            new_ability["name"] = ability[0]
            new_ability["modifier"] = int(ability[2])
            new_ability["keywords"] = []
            parse_advantage(ability, 3, new_ability["keywords"])
            self.abilities.append(new_ability)

        for save in saves:
            new_save = {}
            new_save["name"] = save[0]
            if system == "dnd5":
                new_save["modifier"] = int(save[2])
            else:
                new_save["modifier"] = int(save[3])
            new_save["keywords"] = []
            parse_advantage(save, 3, new_save["keywords"])
            self.saves.append(new_save)

        for skill in skills:
            new_skill = {}
            new_skill["name"] = skill[0]
            if system == "dnd5":
                new_skill["modifier"] = int(skill[2])
            else:
                new_skill["modifier"] = int(skill[3])
            new_skill["keywords"] = []
            parse_advantage(skill, 3, new_skill["keywords"])
            self.skills.append(new_skill)

        for attack in attacks:
            new_attack = {}

            new_attack["name"] = attack[0]
            new_attack["hit"] = int(attack[1])
            new_attack["damage"] = attack[2]
            new_attack["keywords"] = []

            new_attack_group: int = 0
            new_attack_critrange: int = 20
            new_attack_critmultiplier: int = 2

            if system == "dnd5":
                new_attack_group = parse_optional_int(attack, 3, new_attack_group)
                new_attack_critrange = parse_optional_int(attack, 4, new_attack_critrange)

                parse_advantage(attack, 4, new_attack["keywords"])
            else:
                new_attack_critrange = parse_optional_int(attack, 3, new_attack_critrange)
                new_attack_critmultiplier = parse_optional_int(attack, 4, new_attack_critmultiplier)

                parse_advantage(attack, 5, new_attack["keywords"])

                if new_attack["name"].lower().endswith("[2h]"):
                    new_attack["name"] = new_attack["name"][:-4].strip()
                    new_attack["keywords"].append("2h")

            new_attack["group"] = new_attack_group
            new_attack["critrange"] = new_attack_critrange
            new_attack["critmultiplier"] = new_attack_critmultiplier

            self.attacks.append(new_attack)

    async def commit(self):
        if self._collection is None:
            return

        await self._collection.update_one(
            {
                "channel": str(self.channel),
                "name": str(self.name)
            },
            {"$set": self.to_dict()},
            upsert=True
        )

    async def delete(self):
        if self._collection is None:
            return

        if self._id is None:
            return

        await self._collection.find_one_and_delete(
            {"_id": self._id}
        )

    def get_ability(self, name: str) -> dict:
        for ability in self.abilities:
            ability_name: str = ability["name"]
            if ability_name.lower().startswith(name.lower()):
                return ability

        return None

    def get_save(self, name: str) -> dict:
        for save in self.saves:
            save_name: str = save["name"]
            if save_name.lower().startswith(name.lower()):
                return save

        return None

    def get_skill(self, name: str) -> dict:
        for skill in self.skills:
            skill_name: str = skill["name"]
            if skill_name.lower().startswith(name.lower()):
                return skill

        return None

    def get_attacks(self, name: str) -> list[dict]:
        attack_group = 0

        # Find single attack, or determine group
        for attack in self.attacks:
            attack_name: str = attack["name"]
            if attack_name.lower().startswith(name.lower()):
                if attack["group"] == 0:
                    return [attack]  # Make sure to return a list

                attack_group = attack["group"]
                break

        # No attack found
        if attack_group == 0:
            return None

        # Find all attacks for group
        attacks = []

        for attack in self.attacks:
            if attack["group"] == attack_group:
                attacks.append(attack)

        return attacks

    @classmethod
    def create(cls, collection: Collection, channel: int, sheet_url: str) -> Character:
        character = cls()

        character._collection = collection
        character.channel = channel
        character.sheet = gspread.utils.extract_id_from_url(sheet_url)

        return character

    @classmethod
    async def get_all(cls, collection: Collection, channel: int) -> list[Character]:
        result_list = collection.find(
            {"channel": str(channel)}
        )

        character_list = []

        async for result_dictionary in result_list:
            character = Character.from_dict(result_dictionary)
            character._collection = collection
            character_list.append(character)

        return character_list

    @classmethod
    async def get(cls, collection: Collection, channel: int, name: str, exact: bool = False) -> Character:
        if exact:
            name_filter = name
        else:
            name_filter = re.compile(name, re.IGNORECASE)

        result_dictionary = await collection.find_one(
            {
                "channel": str(channel),
                "name": name_filter
            }
        )

        if result_dictionary is None:
            return None

        character = Character.from_dict(result_dictionary)
        character._collection = collection

        return character

    # Serialization

    def to_dict(self):
        return {
            "channel": str(self.channel),
            "sheet": self.sheet,
            "system": self.system,
            "name": self.name,
            "portrait": self.portrait,
            "initiative": self.initiative,
            "abilities": self.abilities,
            "saves": self.saves,
            "skills": self.skills,
            "attacks": self.attacks
        }

    @classmethod
    def from_dict(cls, dct) -> Character:
        character = cls()

        character._id = dct["_id"]
        character.channel = int(dct["channel"])
        character.sheet = dct["sheet"]
        character.system = dct["system"]
        character.name = dct["name"]
        character.portrait = dct["portrait"]
        character.initiative = dct["initiative"]
        character.abilities = dct["abilities"]
        character.saves = dct["saves"]
        character.skills = dct["skills"]
        character.attacks = dct["attacks"]

        return character
