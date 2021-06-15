import d20
from npchelper_dnd5e import NpcHelper_Dnd5e

npc = NpcHelper_Dnd5e()
#npc.update_character_by_id(1)
#npc.update_character_by_id(2)

#print(npc.get_attack(2, "d"))

roll = "2d6+4d6+3"
roll_parts = roll.split("d", 1)
roll_parts[0] = str(int(roll_parts[0])*2)
roll_crit = "d".join(roll_parts)
print(roll_crit)

#result = d20.roll("1d20")
#print(result)
#print(result.crit)
#if result.crit == d20.dice.CritType.CRIT:
#    print("Crit!")
#elif result.crit == d20.dice.CritType.FAIL:
#    print("Critical miss!")
