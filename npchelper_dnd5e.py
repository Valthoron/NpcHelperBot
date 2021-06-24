import gspread
import sqlite3

def make_key(name):
    return "".join(name.split()).lower()

class NpcHelper_Dnd5e:
    def __init__(self):
        self.database_connection = sqlite3.connect('NpcHelper.db')
        self.database_connection.row_factory = sqlite3.Row
        self.database = self.database_connection.cursor()

        self.gsheet_service = gspread.service_account(filename="client_secret.json")

    def add_character(self, url, channel, server):
        key = gspread.utils.extract_id_from_url(url)

        self.database.execute("INSERT INTO characters (gsheet, channel, server) VALUES (:gsheet, :channel, :server)",
            {
                "gsheet": key,
                "channel": channel,
                "server": server
            })

        self.database_connection.commit()

        character_id = self.database.lastrowid

        self.update_character_by_id(character_id)
        return self.get_character_by_id(character_id)

    def remove_character(self, cid):
        self.database.execute("DELETE FROM characters WHERE id=:id", {"id": cid})
        self.database.execute("DELETE FROM checks WHERE character_id=:id", {"id": cid})
        self.database_connection.commit()

    def update_character_by_id(self, cid):
        # Get character sheet
        row = self.database.execute("SELECT * FROM characters WHERE id=:id",
            {
                "id": cid
            }
            ).fetchone()

        if row is None:
            return False

        sheet = self.gsheet_service.open_by_key(row["gsheet"]).get_worksheet(0)

        # Tabula rasa
        self.database.execute("DELETE FROM checks WHERE character_id=:id", {"id": cid})
        self.database.execute("DELETE FROM attacks WHERE character_id=:id", {"id": cid})

        # Parse character sheet
        system = sheet.get("system").first()
        character_name = sheet.get("name").first()
        portrait_url = sheet.get("portrait").first()
        abilities = sheet.get("Abilities")
        saves = sheet.get("Saves")
        skills = sheet.get("Skills")
        attacks = sheet.get("Attacks")

        self.database.execute("UPDATE characters SET name=:name, system=:system, portrait=:portrait WHERE id=:id",
            {
                "id": cid,
                "name": character_name,
                "system": system,
                "portrait": portrait_url
            })

        for ability in abilities:
            ability_name = ability[0]
            ability_key = make_key(ability_name)
            ability_modifier = ability[2]
            self.database.execute("INSERT INTO checks (character_id, key, name, modifier) VALUES (:id, :key, :name, :modifier)",
            {
                "id": cid,
                "key": ability_key,
                "name": ability_name,
                "modifier": ability_modifier
            })

        for save in saves:
            save_name = save[0]
            save_key = "save_" + make_key(save[0])
            save_modifier = save[2]
            self.database.execute("INSERT INTO checks (character_id, key, name, modifier) VALUES (:id, :key, :name, :modifier)",
            {
                "id": cid,
                "key": save_key,
                "name": save_name,
                "modifier": save_modifier
            })

        for skill in skills:
            skill_name = skill[0]
            skill_key = make_key(skill_name)
            if system == "dnd3.5":
                skill_modifier = skill[3]
            else:
                skill_modifier = skill[2]
            self.database.execute("INSERT INTO checks (character_id, key, name, modifier) VALUES (:id, :key, :name, :modifier)",
            {
                "id": cid,
                "key": skill_key,
                "name": skill_name,
                "modifier": skill_modifier
            })

        for attack in attacks:
            attack_name = attack[0]
            attack_key = make_key(attack_name)
            attack_hit = attack[1]
            attack_damage = attack[2]

            if system == "dnd5":
                if len(attack) > 3:
                    attack_group = attack[3]
                else:
                    attack_group = 0

                attack_critrange = 20
                attack_critmultiplier = 2
            else:
                if len(attack) > 3:
                    attack_critrange = attack[3]
                    attack_critmultiplier = attack[4]
                else:
                    attack_critrange = 20
                    attack_critmultiplier = 2

                attack_group = 0


            self.database.execute("INSERT INTO attacks (character_id, name, key, hit, damage, multigroup, critrange, critmultiplier) VALUES (:id, :name, :key, :hit, :damage, :group, :critrange, :critmultiplier)",
            {
                "id": cid,
                "name": attack_name,
                "key": attack_key,
                "hit": attack_hit,
                "damage": attack_damage,
                "group": attack_group,
                "critrange": attack_critrange,
                "critmultiplier": attack_critmultiplier
            })

        # Finally commit
        self.database_connection.commit()

        return True

    def find_all_characters(self, channel, server):
        rows = self.database.execute("SELECT id, name, system, portrait FROM characters WHERE server=:server AND channel=:channel",
            {
                "server": server,
                "channel": channel
            })

        characters = []

        for row in rows:
            characters.append({ "id": row["id"], "name": row["name"], "system": row["system"], "portrait": row["portrait"] })

        return (len(characters) > 0), characters

    def get_character(self, name, channel, server):
        row = self.database.execute("SELECT id, name, system, portrait FROM characters WHERE name LIKE :name AND server=:server AND channel=:channel",
            {
                "name": name + "%",
                "server": server,
                "channel": channel
            }).fetchone()

        if row is None:
            return False, -1

        return True, { "id": row["id"], "name": row["name"], "system": row["system"], "portrait": row["portrait"] }

    def get_character_by_id(self, cid):
        row = self.database.execute("SELECT id, name, system, portrait FROM characters WHERE id=:id",
            {
                "id": cid
            }).fetchone()

        if row is None:
            return False, -1

        return True, { "id": row["id"], "name": row["name"], "system": row["system"], "portrait": row["portrait"] }

    def get_check(self, cid, name):
        key = make_key(name)

        row = self.database.execute("SELECT name, modifier FROM checks WHERE character_id=:id AND key LIKE :key",
            {
                "id": cid,
                "key": key + "%"
            }).fetchone()

        if row is None:
            return False, None

        return True, { "name": row["name"], "modifier": row["modifier"] }

    def get_attack(self, cid, name):
        key = make_key(name)

        row = self.database.execute("SELECT name, hit, damage, multigroup, critrange, critmultiplier FROM attacks WHERE character_id=:id AND key LIKE :key",
            {
                "id": cid,
                "key": key + "%"
            }).fetchone()

        if row is None:
            return False, None

        group = row["multigroup"]

        if group == 0:
            return True, [{ "name": row["name"], "hit": row["hit"], "damage": row["damage"], "critrange": row["critrange"], "critmultiplier": row["critmultiplier"] }]

        rows = self.database.execute("SELECT name, hit, damage, critrange, critmultiplier FROM attacks WHERE character_id=:id AND multigroup=:group",
            {
                "id": cid,
                "group": group
            })

        all_attacks = []

        for row in rows:
            all_attacks.append({ "name": row["name"], "hit": row["hit"], "damage": row["damage"], "critrange": row["critrange"], "critmultiplier": row["critmultiplier"] })

        return True, all_attacks
