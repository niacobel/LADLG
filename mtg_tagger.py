#!/usr/bin/env python3

########################################################################################################################################################
##                                                                     MTG TAGGER                                                                     ##
##                                                                                                                                                    ##
#!                                    This script prepares the input files needed to run the QOCT-RA program by extracting                            ##
#!                                  information from a given source file and launches the corresponding jobs on the cluster.                          ##
#!                                      Extended documentation is available at https://chains-ulb.readthedocs.io/                                     ##
##                                                                                                                                                    ##
##                                   /!\ In order to run, this script requires Python 3.5+ as well as Scrython. /!\                                   ##
########################################################################################################################################################

import os
import re
import shutil
import time

import scrython

import other_functions as of

# =================================================================== #
# =================================================================== #
#                       DEFINE TAGGING FUNCTIONS                      #
# =================================================================== #
# =================================================================== #

def automatic_tags(card:dict, catalogs_list:list):
  """
  Automatically define tags for the card based on Scryfall data by calling other functions for each category of tags.
  Supported categories:
    - Keywords (from Scryfall)
    - Characteristics of the card (anything outside the rules text and the name)
    - Triggers of the card (conditions for the triggered abilities of the card to trigger)
    - Costs of the card (additional costs to use the abilities of the card) 
    - Effects of the card (what the abilities of the card do, rather than how they can be activated/triggered)
  """

  auto_tags = {}

  # ================
  # Preparation step
  # ================

  # Get all names of the card

  names = []

  if "card_faces" in card:
    for face in range(len(card['card_faces'])):
      names.append(card['card_faces'][face]['name'])
      if "legendary" in card['card_faces'][face]['type_line'].lower():
        names.extend(name_shortener(card['card_faces'][face]['name']))

  else:
    names.append(card['name'])
    if "legendary" in card['type_line'].lower():
      names.extend(name_shortener(card['name']))

  # Merge oracle texts for DFCs

  if "card_faces" in card: 
    oracle_text = card['card_faces'][0]['oracle_text'] + "\n" + card['card_faces'][1]['oracle_text']
  else:
    oracle_text = card['oracle_text']

  # Remove reminder text from oracle text

  oracle_text = re.sub(r'\([^()]*\)', '', oracle_text)

  # Declare catalogs argument as a global variable

  global catalogs
  catalogs = catalogs_list

  # ========
  # Get TAGs
  # ========

  # Keywords of the card (as given by Scryfall)

  auto_tags['keywords'] = [keyword.lower() for keyword in card['keywords']]

  # Characteristics of the card (anything outside the rules text and the name)

  auto_tags['characteristics'] = charac_tags(card)

  # Triggers of the card (conditions for the triggered abilities of the card to trigger)

  auto_tags['triggers'] = triggers_tags(card,names,oracle_text)

  # Costs of the card (additional costs to use the abilities of the card)

  auto_tags['costs'] = costs_tags(card,names,oracle_text)

  # Effects of the card (what the abilities of the card do, rather than how they can be activated/triggered)

  auto_tags['effects'] = effects_tags(card,names,oracle_text)

  return auto_tags
   
#############################################################################################

def name_shortener(name:str):
  """
  Approximatively shortens the name of the card, because legendaries sometimes refer to themselves in shorter ways
  """
  
  short_names = []

  if ", " in name:
    short_names.append(name.split(",")[0].strip())
  elif len(name.split(" ")) == 2:
    for word in name.split(" "):
      short_names.append(word)
  
  return short_names

#############################################################################################

def search_oracle(pattern:str,text:str):
  """
  Searches the text for a specific case-insensitive pattern and return True/False depending on whether the pattern is found or not.
  Also takes into account the possiblity of extra spaces between words.
  """

  result = re.compile(pattern.replace(" ","\s+"), re.IGNORECASE).search(text)
  return result

#############################################################################################

def sort_captured(captured_words:str):
  """
  Sort words captured through a regex, trying to identify the mentioned card types and subtypes.
  """

  split_words = re.split(r",| ", captured_words)
  types_list = [word.lower() for word in split_words if word.lower() in catalogs or (word.lower()).lstrip("non") in catalogs]

  return types_list

#############################################################################################

def charac_tags(card:dict):
  """
  Automatically define "Characteristics" tags for the card based on Scryfall data.
  "Characteristics" tags refer to anything outside the rules text and the name of the card.
  Supported tags:
    - Number of colours: colourless, mono- or multicoloured
    - Type line: anything that is included in the type line (supertypes, types and subtypes)
  """

  tags = []

  # Number of colours

  if "card_faces" in card and "Adventure" not in card['type_line']:
    colours_front = card['card_faces'][0]['colors']
    colours_back = card['card_faces'][1]['colors']
    if len(colours_front) == 0 or len(colours_back) == 0:
      tags.append('colourless')    
    if len(colours_front) == 1 or len(colours_back) == 1:
      tags.append('monocoloured')
    if len(colours_front) > 1 or len(colours_back) > 1:
      tags.append('multicoloured')
  else:
    colours = card['colors']
    if len(colours) == 0:
      tags.append('colourless')    
    if len(colours) == 1:
      tags.append('monocoloured')
    if len(colours) > 1:
      tags.append('multicoloured')

  # Irreducible cost (no generic mana)

  if "card_faces" in card:
    mana_costs = [card['card_faces'][0].get('mana_cost'),card['card_faces'][1].get('mana_cost')]
  else:
    mana_costs = [card.get('mana_cost')]

  if True not in [any([symbol.isdigit() for symbol in mana_cost]) for mana_cost in mana_costs]:
    tags.append('irreducible')

  # Type line

  if "card_faces" in card:
    lines = [card['type_line'].partition("//")[0],card['type_line'].partition("//")[2]]
    types = []
    subtypes = []
    for line in lines:
      types.extend(line.partition("\u2014")[0].split(" "))
      subtypes.extend(line.partition("\u2014")[2].split(" "))
    types = list(dict.fromkeys(types))
    subtypes = list(dict.fromkeys(subtypes))
  else:
    types = card['type_line'].partition("\u2014")[0].split(" ")
    subtypes = card['type_line'].partition("\u2014")[2].split(" ")

  for type in types:
    if type != "":
      tags.append('type_' + type.lower())
  
  for type in subtypes:
    if type != "":
      tags.append('subtype_' + type.lower())

  # Power / Toughness

  if 'power' in card or 'power' in card.get('card_faces','no'):
    for key in 'power','toughness':
      if "card_faces" in card:
        val_front = card['card_faces'][0].get(key,'no')
        if val_front != 'no':
          tags.append('%s_%s' % (key,val_front))
        val_back = card['card_faces'][1].get(key,'no')
        if val_back != 'no':
          tags.append('%s_%s' % (key,val_back))
      else:
        tags.append('%s_%s' % (key,card[key]))

  # Set

  tags.append("set_" + card['set'])

  return tags

#############################################################################################

def triggers_tags(card:dict,names:list,oracle_text:str):
  """
  Automatically define "Triggers" tags for the card based on Scryfall data, its name(s) and its oracle text(s).
  "Triggers" tags refer to conditions for the triggered abilities of the card to trigger.
  Supported tags:
    - Attack
    - Block
    - Cast(_type) and self_cast
    - Combat
    - Death
    - End_step
    - ETB and other_ETB
    - Landfall
    - Saboteur
    - Upkeep
  """

  tags = []

  # Attack

  pattern1 = r"when(?:ever)? [^\.]* attacks?"
  pattern2 = r"when(?:ever)? [^\.]* attacks? you"
  if search_oracle(pattern1,oracle_text) and not search_oracle(pattern2,oracle_text):
    tags.append('attack')

  # Block

  pattern = r"when(?:ever)? [^\.]* blocks?"
  if search_oracle(pattern,oracle_text):
    tags.append('block')

  # Cast and self_cast
  
  for name in names:
    pattern = r"when(?:ever)? " + name + r"[^\.]* enters? the battlefield[\w\s]*, (?:if you cast it|if it was kicked|if its \w+ cost was paid)"
    if search_oracle(pattern,oracle_text):
      tags.append('self_cast')
      break

  pattern = r"when(?:ever)? you cast this spell"
  if search_oracle(pattern,oracle_text):
    tags.append('self_cast')

  pattern = r"when(?:ever)? you cast a spell"
  if search_oracle(pattern,oracle_text):
    tags.append('cast_all')

  pattern = r"when(?:ever)? you cast an? (?P<card_types>[^\.]*) spell,"
  if search_oracle(pattern,oracle_text):
    types_list = sort_captured(search_oracle(pattern,oracle_text).group("card_types"))
    for word in types_list:
      tags.append('cast_' + word)

  # Combat

  pattern = r"at the beginning of combat"
  if search_oracle(pattern,oracle_text):
    tags.append('combat')

  # Death

  pattern1 = r"when(?:ever)? [^\.]* dies?"
  pattern2 = r"when(?:ever)? [^\.]*(?:opponent|dealt (?:combat )*damage)+[^\.]* dies?"
  if search_oracle(pattern1,oracle_text) and not search_oracle(pattern2,oracle_text):
    tags.append('death')  

  # End_step

  pattern = r"at the beginning of (?:the|your|each(?: player's)?) end step"
  if search_oracle(pattern,oracle_text):
    tags.append('end_step')

  # ETB and other_ETB

  for name in names:
    pattern = r"when(?:ever)? " + name + r"[^\.]* enters? the battlefield(?![^\.]*(?:if you cast it|if it was kicked|if its \w+ cost was paid))"
    if search_oracle(pattern,oracle_text):
      tags.append('etb')
      break

  if "etb" not in tags and "all_parts" in card:
    for part in card['all_parts']:
      if part['component'] == 'token': # For cards that create tokens with ETB
        pattern = r"when(?:ever)? this creature[^\.]* enters? the battlefield(?![^\.]*(?:if you cast it|if it was kicked|if its \w+ cost was paid))"
        if search_oracle(pattern,oracle_text):
          tags.append('etb')
          break

  pattern = r"when(?:ever)? [^\.]*another [^\.]* enters? the battlefield(?![^\.]*(?:if you cast it|if it was kicked|if its \w+ cost was paid))"
  if search_oracle(pattern,oracle_text):
    tags.append('other_etb')

  # Landfall

  pattern = r"when(?:ever)? [^\.]* lands? enters? the battlefield(?! under an opponent's control)"
  if search_oracle(pattern,oracle_text):
    tags.append('landfall')

  # Saboteur

  pattern = r"when(?:ever)? [^\.]* deals? (?:combat )?damage to an? (?:player|opponent)"
  if search_oracle(pattern,oracle_text):
    tags.append('saboteur')

  # Upkeep

  pattern = r"at the beginning of (?:your|each(?: player's)?) upkeep"
  if search_oracle(pattern,oracle_text):
    tags.append('upkeep')

  return tags

#############################################################################################

def costs_tags(card:dict,names:list,oracle_text:str):
  """
  Automatically define "Costs" tags for the card based on Scryfall data, its name(s) and its oracle text(s).
  "Costs" tags refer to additional costs that must be paid in order to use the abilities of the card.
  Supported tags:
    - Mana_sink
    - Tap
  """

  tags = []

  # Mana Sink

  pattern1 = r"(?:\{[WUBRGCX0-9]+\})+[^\.]*:"
  pattern2 = r"you (?:may )?pay (?:\{[WUBRGCX0-9]+\})+"
  if search_oracle(pattern1,oracle_text) or search_oracle(pattern2,oracle_text):
    tags.append('mana_sink') 

  # Tap

  pattern = r'{T}'
  if search_oracle(pattern,oracle_text):
    tags.append('tap') 

  return tags

#############################################################################################

def effects_tags(card:dict,names:list,oracle_text:str):
  """
  Automatically define "Effects" tags for the card based on Scryfall data, its name(s) and its oracle text(s).
  "Effects" tags refer to what the abilities of the card do, rather than how they can be activated/triggered.
  Supported tags:
    - Burn and Faceburn
    - Coin_flip
    - Counters and other_Counters
    - Draw
    - Die_roll
    - Extra_combat
    - Initiative
    - Looter
    - Monarch
    - Reanimate and self_reanimate
    - Recast(_type) and self_recast
    - Recursion(_type) and self_recursion
    - Tokens(_type)
    - Uncounterable
    - Wheel
  """

  tags = []

  # Burn and Faceburn

  pattern1 = r"deals? [^\.,]*damage (?!to target (?:player|opponent))(?:equal to [^\.,]*)?(?:to any target|to [^\.,]* creature|divided as you choose among [^\.,]* (?:targets|[^\.,]* creature))"
  pattern2 = r"deals? [^\.,]*damage to (?:each|target|the|that) (?:player|opponent)(?: or planeswalker)? and (?:each [^\.,]*creature|[^\.,]* damage to [^\.,]*creature)"
  if search_oracle(pattern1,oracle_text) or search_oracle(pattern2,oracle_text):
    tags.append('burn')

  pattern = r"deals? [^\.,]*damage to (?:each|target|the|that|its) (?:player|opponent|controller)"
  if search_oracle(pattern,oracle_text) and 'burn' not in tags:
    tags.append('faceburn')

  # Coin_flip

  pattern = r"flips? \w+ coins?"
  if search_oracle(pattern,oracle_text):
    tags.append('coin_flip')

  # Counters and other_Counters

  patterns = []
  for name in names:
    patterns.append(r"puts? [^\.]* counters? on (?:" + name + r"|each creature|each permanent)")
    patterns.append(name + r" enters? the battlefield with [^\.]* counters? on it")
    patterns.append(r"distributes? [^\.]* counters? among any number of target ")
    if any([search_oracle(pattern,oracle_text) for pattern in patterns]):
      tags.append('counters')
      break

  pattern1 = r"puts? [^\.]* counters? on (?:it|each|target|another|a |that)"
  pattern2 = r"distributes? [^\.]* counters? among"
  if search_oracle(pattern1,oracle_text) or search_oracle(pattern2,oracle_text):
    tags.append('other_counters')

  # Draw

  pattern1 = r"(?!opponent )draws?\s*\w*\s*cards?(?:\.| for| equal| and)"
  pattern2 = r"(?!opponent )draws? [^\.]* then discards?" # Looter tag insted
  pattern3 = r"(?!opponent )discards? (?:your hand|their hand|any number of cards)[^\.]* (?:and|then) draws?" # Wheel tag instead
  if search_oracle(pattern1,oracle_text) and not search_oracle(pattern2,oracle_text) and not search_oracle(pattern3,oracle_text):
    tags.append('draw')

  # Die_roll

  pattern = r"rolls? \w+ d\d+"
  if search_oracle(pattern,oracle_text):
    tags.append('die_roll')

  # Extra Combat

  pattern = r"additional combat phase"
  if search_oracle(pattern,oracle_text):
    tags.append('extra_combat')

  # Initiative

  pattern = r"you take the initiative"
  if search_oracle(pattern,oracle_text):
    tags.append('initiative')

  # Looter

  pattern = r"(?!opponent )draws? [^\.]* then discards?"
  if search_oracle(pattern,oracle_text):
    tags.append('looter')

  # Monarch

  pattern = r"you become the monarch"
  if search_oracle(pattern,oracle_text):
    tags.append('monarch')

  # Reanimate and self_reanimate

  pattern = r"(?:put|return) (?P<card_types>[^\.]*) cards? [^\.,]*from[^\.,]* graveyards? (?:onto|to) the battlefield"
  if search_oracle(pattern,oracle_text):
    types_list = sort_captured(search_oracle(pattern,oracle_text).group("card_types"))
    for word in types_list:
      tags.append('reanimate_' + word)

  for name in names:
    pattern = r"return " + name + r" from your graveyard to the battlefield"
    if search_oracle(pattern,oracle_text):
      tags.append('self_reanimate')
      break

  # Recast and self_recast

  pattern = r"you may(?: play lands and)? cast (?:cards?|spells?) from your graveyard"
  if search_oracle(pattern,oracle_text):
      tags.append('recast_all')

  pattern = r"you may(?: play a land and)? cast (?P<card_types>[^\.]*) (?:cards?|spells?)[^\.]* from your graveyard"
  if search_oracle(pattern,oracle_text):
    types_list = sort_captured(search_oracle(pattern,oracle_text).group("card_types"))
    for word in types_list:
      tags.append('recast_' + word)

  for name in names:
    pattern = r"cast " + name + r" from your graveyard(?! (?:onto|to) the battlefield)"
    if search_oracle(pattern,oracle_text):
      tags.append('self_recast')
      break
  
  # Recursion and self_recursion

  pattern = r"return (?:all|[^\.]*target) cards? from your graveyard to your hand"
  if search_oracle(pattern,oracle_text):
      tags.append('recursion_all')

  pattern = r"return (?P<card_types>[^\.]*) cards? from your graveyard to your hand"
  if search_oracle(pattern,oracle_text):
    types_list = sort_captured(search_oracle(pattern,oracle_text).group("card_types"))
    for word in types_list:
      tags.append('recursion_' + word)

  for name in names:
    pattern = r"return " + name + r" from your graveyard to your hand"
    if search_oracle(pattern,oracle_text):
      tags.append('self_recursion')
      break

  # Tokens

  if "all_parts" in card:
    for part in card['all_parts']:
      if part['component'] == 'token':
        types_list = [word for word in part['type_line'].split(" ") if word != "\u2014" and word.lower() != "token"]
        for word in types_list:
          if ('tokens_' + word).lower() not in tags:
            tags.append('tokens_' + word.lower())

  # Uncounterable

  pattern = r"this spell can't be countered"
  if search_oracle(pattern,oracle_text):
    tags.append('uncounterable')

  # Wheel

  pattern = r"(?!opponent )discards? (?:your hand|their hand|any number of cards)[^\.]* (?:and|then) draws?"
  if search_oracle(pattern,oracle_text):
    tags.append('wheel')

  return tags

# =================================================================== #
# =================================================================== #
#                         DEFINE MAIN FUNCTION                        #
# =================================================================== #
# =================================================================== #

def main(): 

  # Load Scryfall catalogs

  catalog_file = "catalogs.txt"

  if not os.path.exists(catalog_file):
    of.get_catalog(catalog_file)

  with open(catalog_file, 'r') as f:
    catalogs = f.read().splitlines()

  # Fetch card data

  print("\nWhich MTG card would you like to check tags for?")

  def fetch_data():

    inp_name = input("Enter a card name then press ENTER: ")
    print("")

    try:

      print("{:20}".format("Fetching data ..."), end ="")
      search = scrython.cards.Search(q='!"%s" include:extras -is:reprint' % inp_name)
      card_data = search.data()[0]
      time.sleep(0.5)
      print("[DONE]")
      return card_data

    except scrython.foundation.ScryfallError as error:

      print("\nERROR: ", error)
      return fetch_data()
  
  card_data = fetch_data() 

  # Print card data (as shown on https://github.com/NandaScott/Scrython/blob/master/examples/get_and_format_card.py)

  console_message = "Card data"
  print("")
  print(console_message)
  print(''.center(len(console_message), '='))
  print("")

  def show_data(card:dict):
    
    if card.get('power'):
        PT = "({}/{})".format(card['power'], card['toughness'])
    else:
        PT = ""

    mana_cost = card.get('mana_cost',0)

    string = ("{cardname} {mana_cost} \n\n{type_line}\n\n{oracle_text}" + ("\n\n{power_toughness}" if PT != "" else "")).format(
      cardname=card['name'],
      mana_cost=mana_cost,
      type_line=card['type_line'],
      oracle_text=card['oracle_text'],
      power_toughness=PT
      )

    return string

  if "card_faces" in card_data:
    for face in card_data['card_faces']:
      print(show_data(face))
      if face == card_data['card_faces'][0]:
        print("\n//\n")
  else:
    print(show_data(card_data))

  # Print TAGs

  console_message = "TAGs"
  print("")
  print(console_message)
  print(''.center(len(console_message), '='))
  print("")

  print("{:20}".format("Computing tags ..."), end ="")
  auto_tags = automatic_tags(card_data, catalogs)
  print("[DONE]")

  print("")
  for category in auto_tags.keys():
    tags = ", ".join(list(map(str.lower,auto_tags[category])))
    print("{:<15} : {:<200}".format(category.capitalize(),tags))
  
  answer = of.askYesNoQuestion("\nWould you like to check tags for another MTG card? (Y/N)\n")

  if answer.startswith('Y'):
    return main()
  elif answer.startswith('N'):
    print("\nEND OF CODE EXECUTION")

# =================================================================== #
# =================================================================== #
#                          CALL MAIN FUNCTION                         #
# =================================================================== #
# =================================================================== #

if __name__ == "__main__":

  columns, rows = shutil.get_terminal_size()
  print("".center(columns,"~"))
  print("")
  print("WELCOME TO THE MTG TAGGER".center(columns))
  print("")
  print("".center(columns,"~"))

  # Call main function

  main()