import json
import re
import time

import scrython


def ask_nb_in_range(question:str,min_int:int,max_int:int):
  """
  Asks the user a question that must be answered by an integer comprised in a certain range.
  """

  number = input(question)
  if not number.isnumeric() or int(number) < min_int or int(number) > max_int:
    print("Please enter an integer comprised between %s and %s." % (min_int,max_int))
    return ask_nb_in_range(question,min_int,max_int)
  else:
    return number

#############################################################################################

def askYesNoQuestion(question:str):
  """
  Asks the user a question that must be answered by a string beginning by either Y or N (this is not case sensitive).
  """

  YesNoAnswer = input(question).upper()
  if YesNoAnswer.startswith('Y') or YesNoAnswer.startswith('N'):
    return YesNoAnswer
  else:
    print("Please answer by either 'Yes' or 'No'.")
    return askYesNoQuestion(question)

#############################################################################################

def parse_list(file:str):

  """Parses the content of a text file containing the list of all cards included in the card pile and their associated tags, as formatted by the Moxfield website.

    Parameters
    ----------
    file : str
        Path to the text file containing the list, relative to this script.
    
    Returns
    -------
    cards_list : dict
        The extracted information of the text file. Each key corresponds to the card name and its value is a list of the associated tags.
  
  """

  cards_pile = {}

  with open(file, 'r') as f:
    cards_from_file = f.read().splitlines()
    
  # Pattern for finding lines looking like '1 Silumgar, the Drifting Death *F* #Attack #Self-Protection #Sweeper #Tribal'
  line_pattern = re.compile(r"^\d\s(?P<name>[\w\s\-,'&\/]+)(?:\s\(\w+\))?(?:\s\*\w\*)?(?:\s+(?P<tags>#.*)$|$)")

  for line in cards_from_file:
    if line_pattern.match(line):
      
      card_name = line_pattern.match(line).group('name')
      card_name = re.sub(r"\/", r"//", card_name) # For DFCs, Moxfield only use one slash instead of two
      raw_tags = line_pattern.match(line).group('tags')

      if raw_tags is not None:
        card_tags = raw_tags.split("#")
        card_tags = [tag.strip().lower() for tag in card_tags if tag != ""]
      else:
        card_tags = []

      cards_pile[card_name] = card_tags

  return cards_pile

#############################################################################################

def get_cards_data(cards_pile,file:str):

  """Fetches the scryfall data of each card mentioned in the cards pile and compiles them into a JSON file. This function uses the Scrython module: https://github.com/NandaScott/Scrython

    Parameters
    ----------
    cards_pile : list or dict (iterable)
        Iterable specifying the names of the cards for which data need to be fetched.
    
    file : str
        Path to the JSON file that will be created, relative to this script.
      
  """

  console_message = "Creating or updating the cards data from Scryfall"
  print("")
  print(''.center(len(console_message)+11, '*'))
  print(console_message.center(len(console_message)+10))
  print(''.center(len(console_message)+11, '*'))
  print("")

  data = []

  for i, card_name in enumerate(cards_pile, start=1):
    print('Fetching card: {} | {} of {}'.format(card_name, i, len(cards_pile)))
    search = scrython.cards.Search(q='!"%s" include:extras -is:reprint' % card_name)
    data.append(search.data()[0])
    time.sleep(0.5)

  with open(file, 'w+') as f:
    f.write(json.dumps(data, sort_keys=True, indent=4))

#############################################################################################

def get_catalog(file:str):

  """Fetches the scryfall catalogs subtypes and compiles them into a text file, along with the different card types and supertypes. This function uses the Scrython module: https://github.com/NandaScott/Scrython

    Parameters
    ----------

    file : str
        Path to the text file that will be created, relative to this script.
      
  """

  print("{:<35} ".format("\nFetching catalogs from Scryfall ..."), end="")

  catalogs_list = []

  # Add card types

  catalogs_list.extend(["Creature","Planeswalker","Artifact","Enchantment","Instant","Sorcery","Tribal","Permanent"])

  # Add card supertypes

  catalogs_list.extend(["Basic","Legendary","Snow","World"])

  # Fetch subtypes from scryfall and add them to the list

  crea_types = scrython.catalog.CreatureTypes()
  catalogs_list.extend(crea_types.data())
  time.sleep(0.5)

  pw_types = scrython.catalog.PlaneswalkerTypes()
  catalogs_list.extend(pw_types.data())
  time.sleep(0.5)

  art_types = scrython.catalog.ArtifactTypes()
  catalogs_list.extend(art_types.data())
  time.sleep(0.5)

  ench_types = scrython.catalog.EnchantmentTypes()
  catalogs_list.extend(ench_types.data())
  time.sleep(0.5)

  spell_types = scrython.catalog.SpellTypes()
  catalogs_list.extend(spell_types.data())
  time.sleep(0.5)

  land_types = scrython.catalog.LandTypes()
  catalogs_list.extend(land_types.data())
  time.sleep(0.5)

  # Create the file

  with open(file, 'w+') as f:
    f.write("\n".join([type.lower() for type in catalogs_list]))

  print("{:>10} ".format("[DONE]"))

#############################################################################################

def check_curve(mana_value:int,curve:dict,current_curve:dict):
  """
  Checks if there is still room on the current curve to add the mana value of the current card.
  """

  if mana_value <= min(curve.keys()):
    nb_spots = curve[min(curve.keys())]
    occ_spots = current_curve[min(curve.keys())]
  elif mana_value >= max(curve.keys()):
    nb_spots = curve[max(curve.keys())]
    occ_spots = current_curve[max(curve.keys())]
  else:
    nb_spots = curve[mana_value]
    occ_spots = current_curve[mana_value]

  if occ_spots < nb_spots:
    return True
  else:
    return False

#############################################################################################

def add_to_curve(mana_value:int,current_curve:dict):
  """
  Adds the mana value of the current card to the current curve.
  """

  if mana_value <= min(current_curve.keys()):
    current_curve[min(current_curve.keys())] += 1
  elif mana_value >= max(current_curve.keys()):
    current_curve[max(current_curve.keys())] += 1
  else:
    current_curve[mana_value] += 1

#############################################################################################

def check_hard_costs(mana_costs:list,hard_costs:dict,current_costs:dict):
  """
  Check if the mana cost(s) of the card match one of patterns in hard_costs. It it doesn't, it returns add_card = True. It it does and there is still room for it, it returns add_card = True and indicates the corresponding current_costs number(s) that need to be increased. Otherwise, it returns add_card = False
  """

  # Initialize some variables

  add_card = True
  increase_current_costs = {costs:False for costs in current_costs}

  # Analyze the mana cost(s) in regards to each possible hard costs

  for mana_cost in mana_costs:

    # Extract the colour count from mana cost (e.g. from "{3}{B}{W}{W}" to {'W': 2, 'B': 1})

    colour_cost = re.sub(r"\{|\}|[1-9]",'',mana_cost)
    colour_count = {letter:colour_cost.count(letter) for letter in set(colour_cost)}

    # Iterate over the costs
  
    for costs, number in hard_costs.items():
        
      patterns = costs.split(',')
      patterns = [cost.strip() for cost in patterns if cost != '']
      
      for pattern in patterns:
        
        # Extract the pattern count in the same way as for the mana cost (e.g. from "AADD" to  {'D': 2, 'A': 2})

        pattern_count = {letter:pattern.count(letter) for letter in set(pattern)}
    
        # Check if the pattern cares about both specific and generic colours

        if any(letter in ["W","U","B","R","G","C"] for letter in pattern_count.keys()) and any(letter not in ["W","U","B","R","G","C"] for letter in pattern_count.keys()):
          cares_about_both = True
        else:
          cares_about_both = False
    
        # Check for specific coulours (WUBRGC)

        if any(colour_count.get(letter,0) >= pattern_count.get(letter,float('inf')) for letter in ["W","U","B","R","G","C"]):
          specific_check = True
        else:
          specific_check = False
            
        # Remove data about specific colours that were explicitly mentioned in the pattern

        leftover_cost = list({letter:count for letter,count in colour_count.items() if letter not in pattern_count.keys()}.values())
        leftover_cost_count = {value:leftover_cost.count(value) for value in set(leftover_cost)}
        leftover_pattern = list({letter:count for letter,count in pattern_count.items() if letter not in ["W","U","B","R","G","C"]}.values())
        leftover_pattern_count = {value:leftover_pattern.count(value) for value in set(leftover_pattern)}
        
        # Check for generic colours (other arbitrary letters)

        generic_check = False
        for value, count in leftover_pattern_count.items():
          if count <= sum([co for val, co in leftover_cost_count.items() if val >= value]):
            generic_check = True
        
        # Define if the card can be added or not, and if the current hard costs counters need to be increased

        if (not cares_about_both and (specific_check or generic_check)) or (cares_about_both and specific_check and generic_check):
          if current_costs[costs] == number:
            add_card = False
          else:
            increase_current_costs[costs] = True
            break
  
  if add_card == False:
    return False
  else:
    return increase_current_costs
