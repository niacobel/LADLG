#!/usr/bin/env python3

########################################################################################################################################################
##                                               LIVING ANTHOLOGY DECKS PILE ANALYZER & LIST GENERATOR                                                ##
##                                                                                                                                                    ##
##                                                                                                                                                    ##
##                              /!\ In order to run, this script requires Python 3.5+ as well as Scrython and YAML. /!\                               ##
########################################################################################################################################################

import itertools
import json
import os
import random
import re
import shutil
import statistics
import time
from datetime import date
from typing import OrderedDict

import yaml

import mtg_tagger
import other_functions as of

# If you want to measure the average time of execution, indicate how many times you wish to run it. Otherwise, specify "False"
time_it = False

def main(): 
  # ================
  # Preparation Step
  # ================

  columns, rows = shutil.get_terminal_size()
  print("".center(columns,"~"))
  print("")
  print("WELCOME TO THE LIVING ANTHOLOGY DECKS PILE ANALYZER & LIST GENERATOR".center(columns))
  print("")
  print("".center(columns,"~"))

  # Load the config file

  deck = "dragons"
  config_file = deck + ".yml"

  with open(config_file, 'r', encoding='utf-8') as f_config:
    config = yaml.load(f_config, Loader=yaml.FullLoader)

  # Ask for theme

  notheme_name = "No Theme"
  random_theme_name = "Pick a Theme for Me"
  pile_analysis = "Pile Analysis"

  themes = list(sorted(config['themes'].keys()))
  themes.insert(0,notheme_name)
  if len(themes) > 2:
    themes.append(random_theme_name)
  themes.append(pile_analysis)

  print("\nPlease choose a theme among the following ones by entering its associated number in the console.\n")
  for i in range(len(themes)):
    if themes[i] == notheme_name:
      description = "You're no fun."
    elif themes[i] == random_theme_name:
      description = "I shall do my best for you."
    elif themes[i] == pile_analysis:
      description = "Be prepared to read!"
    else:
      description = config['themes'][themes[i]]['description']
    print('(%s) %s: "%s"' % (i, themes[i], description))

  if time_it:
    inp_number = len(themes) - 1
  else:
    inp_number = int(of.ask_nb_in_range("\nEnter a number then press ENTER: ", 0, len(themes)-1))

  inp_theme = themes[inp_number]

  if inp_theme == notheme_name:
    print("You've chosen no theme, bouh!")
  elif inp_theme == random_theme_name:
    inp_theme = random.choice(themes[1:-1])
    print("""I have chosen the "%s" theme for you. You're welcome!""" % inp_theme)
  elif inp_theme == pile_analysis:
    print("You have chosen to analyze the card pile.")
  else:
    print("""You have chosen the "%s" theme""" % inp_theme)

  # Load general data from config file

  tagger = config['general'].get('auto_tagger', True)
  number_cards = config['general']['number_cards']

  # Load file data from config file

  missing_file = config['files'].get('missing_cards')
  card_pile_file = config['files']['cards_pile']
  json_file = config['files']['scryfall_data']

  # Load the card pile

  card_pile = of.parse_list(card_pile_file)

  # Fetch the data from scryfall if needed (using the scrython module https://github.com/NandaScott/Scrython)

  if not os.path.isfile(json_file):
    # If the file doesn't exist, create it and load it
    of.get_cards_data(card_pile,json_file)
    with open(json_file, 'r') as f:
      scryfall_data = json.load(f)
  else:
    with open(json_file, 'r') as f:
      scryfall_data = json.load(f)
    # If the json file does not include all the cards data, update it and then reload it
    if any(map(lambda name: name not in [card['name'] for card in scryfall_data], [name for name in card_pile.keys()])):
      of.get_cards_data(card_pile,json_file)
      with open(json_file, 'r') as f:
        scryfall_data = json.load(f)

  # Load theme data from config file

  if not config['themes'].get(inp_theme):
    theme_data = { 'tags' : OrderedDict({})}
    smart_fill = False
    banned = []
  else:
    theme_data = config['themes'][inp_theme]
    theme_data['tags'] = OrderedDict((tags.lower(), number) for tags,number in theme_data['tags'].items())
    smart_fill = theme_data.get('smart_fill',True)
    if theme_data.get('ban',None):
      banned = [tag.strip() for tag in theme_data['ban'].split(',') if tag != '']
    else:
      banned = []

  # Update general limitations with theme-specific limitations if needed

  if theme_data.get('limitations'):
    config['limitations'].update(theme_data['limitations'])

  # Load limitations

  curve = config['limitations']['mana_curve']

  if number_cards > sum(curve.values()):
    print("The number of cards in the desired list (%s) is greater than the total number of cards in the desired mana curve (%s)" % (number_cards,sum(curve.values())))
    exit(1)

  hard_costs = config['limitations'].get('hard_costs',{})

  lim_status = {
    'restricted': {'count': 0, 'max': config['limitations'].get('max_restricted',float('inf'))},
    'popular': {'count': 0, 'max': config['limitations'].get('max_pop',float('inf'))},
    'unpopular': {'count': 0, 'max': config['limitations'].get('max_unpop',float('inf'))},
    'illegal': {'count': 0, 'max': config['limitations'].get('max_illegal',float('inf'))},
    'bad_synergy': {'count': 0, 'max': config['limitations'].get('max_bad_synergy',float('inf'))},
    'mana_sink': {'count': 0, 'max': config['limitations'].get('max_sink',float('inf'))}
  }
  
  #! Add limited tags dictionary and counters

  # Load secondary tags

  secondary_tags = config.get('secondary_tags')

  # Define the 25% least popular cards and 25% most popular cards

  ranks = [card['edhrec_rank'] for card in scryfall_data if card.get('edhrec_rank')]
  pile_median = statistics.median(ranks)
  upper_ranks = [rank for rank in ranks if rank < pile_median]
  lower_ranks = [rank for rank in ranks if rank >= pile_median]
  pop_rank_limit = int(statistics.median(upper_ranks))
  unpop_rank_limit = int(statistics.median(lower_ranks))

  # Alter the counters for analysis modes

  if inp_theme == pile_analysis:
    number_cards = len(card_pile)
    curve = {mv : float('inf') for mv in curve}
    for status in lim_status.keys():
      lim_status[status]['max'] = float('inf')
    hard_costs = {costs : float('inf') for costs in hard_costs}

  # Remove the possible missing cards

  if os.path.isfile(missing_file):
    
    with open(missing_file, 'r') as f:
      missing_cards = f.read().splitlines()

    for card in missing_cards:
      card_pile.pop(card, None)

  # Load Scryfall catalogs

  catalog_file = "catalogs.txt"

  if not os.path.exists(catalog_file):
    of.get_catalog(catalog_file)

  with open(catalog_file, 'r') as f:
    catalogs = f.read().splitlines()

  # Initialize some variables

  current_curve = curve.copy()
  current_curve = {mv:0 for mv in current_curve}

  card_list = []
  treated_data = []

  filler_count = 0

  current_costs = hard_costs.copy()
  current_costs = {costs:0 for costs in current_costs}

  prefix_exc = "except_"
  prefix_ign = "ignore_"
  prefix_res = "only_"

  # Print a recap of the cards pile info

  console_message = "General information about the card pile and theme"
  print("")
  print(''.center(len(console_message)+11, '*'))
  print(console_message.center(len(console_message)+10))
  print(''.center(len(console_message)+11, '*'))
  print("")

  console_message = "Card pile characteristics"
  print(console_message)
  print(''.center(len(console_message), '='))
  print("")

  print("{:<35} {:<15}".format("Deck: ", deck))
  print("{:<35} {:<15}".format("Number of cards in the pile: ", len(card_pile)))
  print("{:<35} {:<15}".format("Number of cards of the list: ", number_cards))
  print("{:<35} {:<15}".format("EDHrec rank median: ", pile_median))
  print("{:<35} {:<15}".format("Popular rank limit: ", pop_rank_limit))
  print("{:<35} {:<15}".format("Unpopular rank limit: ", unpop_rank_limit))
  print("{:<35} {:<15}".format("Automatic tagger: ", str(tagger)))
  print("")

  console_message = "Theme characteristics"
  print(console_message)
  print(''.center(len(console_message), '='))
  print("")

  print("{:<35} {:<15}".format("Chosen theme: ", inp_theme))
  print("\nLimitations")
  print(''.center(11, '-'))
  print("")

  if inp_theme != pile_analysis:
    print("Mana curve: \n")
    for mv in sorted(curve.keys()):
      if mv == min(curve.keys()):
        print("{:<25}{:<10} {:<30}".format("MV %s or less: " % mv,curve[mv],''.center(curve[mv], '\u25cf')))
      elif mv == max(curve.keys()):
        print("{:<25}{:<10} {:<30}".format("MV %s or more: " % mv,curve[mv],''.center(curve[mv], '\u25cf')))
      else:
        print("{:<25}{:<10} {:<30}".format("MV %s: " % mv,curve[mv],''.center(curve[mv], '\u25cf')))

  print("")
  for status in lim_status:
      print("{:<35} {:<15}".format("Max number of %s cards: " % status, lim_status[status]['max']))
  print("\nHard costs limitations: ")
  if hard_costs == {}:
    print("- None")
  else:
    for costs,number in hard_costs.items():

      patterns = costs.split(',')
      patterns = [cost.strip() for cost in patterns if cost != '']

      if len(patterns) == 1:
        print("- %s cards with %s pattern" % (number,patterns[0]))
      elif len(patterns) == 2:
        print("- %s cards with %s or %s patterns" % (number,patterns[0],patterns[1]))
      else:
        print("- %s cards with %s, " % (number,patterns[0]), end="")
        print(", ".join(patterns[1:-1]),end="")
        print(" or %s patterns" % patterns[-1])

  print("\nTags")
  print(''.center(4, '-'))
  print("")
  print("{:<35} {:<15}".format("Smart fill: ", str(smart_fill)))
  print("\nTags distribution: ")
  if theme_data['tags'] == {}:
    print("- None")
  else:
    for tags,number in theme_data['tags'].items():

      theme_tags = tags.split(',')
      theme_tags = [tag.strip().upper() for tag in theme_tags if tag != '']
      if len(theme_tags) == 1:
        print("- %s cards with %s" % (number,theme_tags[0]))
      elif len(theme_tags) == 2:
        print("- %s cards with %s or %s" % (number,theme_tags[0],theme_tags[1]))
      else:
        print("- %s cards with %s, " % (number,theme_tags[0]), end="")
        print(", ".join(theme_tags[1:-1]),end="")
        print(" or %s" % theme_tags[-1])

  # ===================
  # Generating the list
  # ===================

  # Shuffle the cards

  names_list = list(card_pile)
  if inp_theme == pile_analysis:
    names_list = sorted(names_list)
  else:
    random.shuffle(names_list)

  # If the smart fill option is enabled, adapt the numbers

  if smart_fill:

    arranged_theme_tags = theme_data['tags'].copy()
    cumulative_number = 0

    for tags,number in theme_data['tags'].items():
      cumulative_number += number
      arranged_theme_tags[tags] = cumulative_number

    theme_data['tags'] = arranged_theme_tags

  # Add a first 'restricted' tag that prioritizes addition of cards restricted to this theme if they are any.

  theme_data['tags']['restricted'] = number_cards
  theme_data['tags'].move_to_end('restricted', last = False) # Bring the 'restricted' key to the start of the dict

  # Add a last 'filler' tag that allows addition of filler cards if needed

  theme_data['tags']['filler'] = number_cards

  # Iterate over the group of tags in the theme and find cards for each of them

  for raw_theme_tags in theme_data['tags'].keys():

    theme_tags = [tag.strip() for tag in raw_theme_tags.split(',') if tag != '']

    if not smart_fill:
      current_number = 0

    for name in names_list:

      # Skip the card if it was already added
      if name in [card['name'] for card in card_list]:
        continue

      # Fetch data about this card if it was not already done
      if name not in [card['name'] for card in treated_data]:
        
        # Get the Scryfall data for this card
        scryfall_card = next(filter(lambda card: card['name'] == name, scryfall_data), None)
        mana_value = int(scryfall_card['cmc'])

        if "card_faces" in scryfall_card:
          mana_costs = [scryfall_card['card_faces'][0]['mana_cost'],scryfall_card['card_faces'][1]['mana_cost']]
        else:
          mana_costs = [scryfall_card['mana_cost']]

        rank = scryfall_card.get('edhrec_rank', pile_median)

        # Get the automatic card tags if needed
        if not tagger:
          auto_tags = {}
          auto_tags_list = []
        else:
          auto_tags = mtg_tagger.automatic_tags(scryfall_card, catalogs)
          auto_tags_list = list(itertools.chain(*list(auto_tags.values()))) #Flatten the list of lists into a single list
          auto_tags_list = list(map(str.lower, auto_tags_list))

          # Remove automatic tags that need to be explicitly ignored

          for tag in [tag for tag in card_pile[name] if tag.startswith(prefix_ign)]:
            ignored = tag.partition(prefix_ign)[2]

            if ignored in auto_tags_list:
              auto_tags_list.remove(ignored)
              for category in auto_tags.keys():
                if ignored in auto_tags[category]:
                  auto_tags[category].remove(ignored)

            elif ignored.endswith("_*"):
              root_tag = ignored.partition("_*")[0]
              for tag in [tag for tag in auto_tags_list if tag.startswith(root_tag)]:
                auto_tags_list.remove(tag)
                for category in auto_tags.keys():
                  if tag in auto_tags[category]:
                    auto_tags[category].remove(tag)

        # Check secondary tags
        if secondary_tags:
          second_tags_list = []
          for new_tag, tags in secondary_tags.items():
            condition_tags = [tag.strip() for tag in tags.split(',') if tag != '']
            if any(tag in card_pile[name] or tag in auto_tags_list for tag in condition_tags if not tag.startswith('-')):
              second_tags_list.append(new_tag)
            elif any(tag[1:] not in card_pile[name] and tag[1:] not in auto_tags_list for tag in condition_tags if tag.startswith('-')):
              second_tags_list.append(new_tag)
          auto_tags_list += second_tags_list
          auto_tags['secondary'] = second_tags_list

        # Merge the automatic tags and the tags of the card pile
        card_tags = card_pile[name] + auto_tags_list
        card_tags = list(dict.fromkeys(card_tags)) # Remove possible duplicates

        # Check statuses
        card_status = {
          'restricted': True if (prefix_res + inp_theme).lower() in card_tags else False,
          'popular': True if rank <= pop_rank_limit else False,
          'unpopular': True if rank >= unpop_rank_limit else False,
          'illegal': True if scryfall_card['legalities']['commander'] != "legal" else False,
          'bad_synergy': True if "bad_synergy" in card_tags else False,
          'mana_sink': True if "mana_sink" in card_tags else False
        }

        # Define the card_data dictionary
        card_data = {
          "name": name,
          "mv": mana_value,
          "mana_costs": mana_costs,
          "tags": card_tags,
          "auto_tags": auto_tags,
          "rank": rank,
          "status" : card_status
        }

        # Add card data to the treated_data list
        treated_data.append(card_data)

      else:
        card_data = next(filter(lambda card: card['name'] == name, treated_data), None)

      # Check hard costs and skip the card if there is no room for it anymore
      increase_current_costs = of.check_hard_costs(card_data['mana_costs'],hard_costs,current_costs)
      if not increase_current_costs:
        continue

      # Skip cards that have been explicitly excluded from this theme
      if (prefix_exc + inp_theme).lower() in card_data['tags'] or any([tag in banned for tag in card_data['tags']]):
        continue

      # Skip cards that cannot be included in this theme
      if any([tag.startswith(prefix_res) for tag in card_data['tags']]) and not card_data['status']['restricted']:
        continue

      # Check the tags in common between the card and the theme
      if raw_theme_tags != 'restricted' and raw_theme_tags != 'filler':
        common_tags = list(set(card_data['tags']).intersection(theme_tags))
      else:
        common_tags = []

      # If any of those conditions is satisfied, then the card is eligible
      eligible = any([
        raw_theme_tags == 'restricted' and card_data['status']['restricted'],
        len(common_tags) > 0,
        raw_theme_tags == 'filler'
      ])

      # If any of those conditions is satisfied, then the card is not eligible
      ineligible = any([
        # Check mana curve
        not of.check_curve(card_data['mv'],curve,current_curve),
        # Check statuses
        any([card_data['status'][status] and lim_status[status]['count'] == lim_status[status]['max'] for status in lim_status])
        #! Check limited tags
      ])

      # Check if the card is eligible and not ineligible
      if eligible and not ineligible:

        # Adjust the relevant counters

        if raw_theme_tags == 'filler':
          filler_count += 1

        for status in card_data['status']:
          if card_data['status'][status]:
            lim_status[status]['count'] += 1

        #! Increase limited tags counters

        for costs in increase_current_costs.keys():
          if increase_current_costs[costs] == True:
            current_costs[costs] += 1

        # If a restricted card was included before a normal card, adjust the theme tags repartition
        if raw_theme_tags == 'restricted':
          for check_tags in theme_data['tags'].keys():
            temp_tags = [tag.strip() for tag in check_tags.split(',') if tag != '']
            # If the card has a tag the theme was looking for, decrease its associated number
            if len(list(set(card_data['tags']).intersection(temp_tags))) > 0:
              theme_data['tags'][check_tags] -= 1
              break
            # If smart fill is on and the card does not match the current tags, increase their associated number as to not penalize them
            elif smart_fill and check_tags != 'restricted':
              theme_data['tags'][check_tags] += 1

        # Define the reason the card was added
        if raw_theme_tags == 'filler':
          reason = "FILLER"
        elif raw_theme_tags == 'restricted':
          reason = "RESTRICTED"
        else:
          reason = ", ".join(map(lambda x:x.upper(),common_tags))

        # Add the card to the list
        of.add_to_curve(card_data['mv'],current_curve)
        print(card_data['name'],': ',card_data['mana_costs'])
        if len(card_data['mana_costs']) > 1 and card_data['mana_costs'][1].strip() != "":
          mana_costs = " // ".join([" ".join(re.sub('[\{\}]', '', cost)) for cost in card_data['mana_costs']])
        else:
          mana_costs = " ".join(re.sub('[\{\}]', '', card_data['mana_costs'][0]))
        card_data.update({
          "mana_costs": mana_costs,
          "reason" : reason
        })
        card_list.append(card_data)

        # Remove card data from the treated_data list
        treated_data.remove(card_data)

        # Check if we need to continue
        if not smart_fill:
          current_number += 1
        else:
          current_number = len(card_list)

        if current_number == theme_data['tags'][raw_theme_tags] or len(card_list) == number_cards:
          break
      
    if len(card_list) == number_cards:
      break

  # Print the list, sorted by mana value

  console_message = "List of chosen cards for the theme %s" % inp_theme
  print("")
  print(''.center(len(console_message)+11, '*'))
  print(console_message.center(len(console_message)+10))
  print(''.center(len(console_message)+11, '*'))
  print("")

  column_sizes = "| {:^70} | {:^24} | {:^24} | {:^12} | {:^80} |"
  table_width = 224
  hrule = " " + ''.center(table_width, '-') + " "
  print(hrule)
  print(column_sizes.format("Name","Mana Cost","Reason","EDHrec Rank","Automatic TAGs (except keywords and characteristics)"))
  print(hrule)

  for mv in sorted(curve.keys()):

    if mv == min(curve.keys()):
      mv_list = [card for card in card_list if card["mv"] <= mv]
      if len(mv_list) > 0:
        print("\t%s cards at mana value %s or less:" % (len(mv_list),mv))
    elif mv == max(curve.keys()):
      mv_list = [card for card in card_list if card["mv"] >= mv]
      if len(mv_list) > 0:
        print("\t%s cards at mana value %s or more:" % (len(mv_list),mv))
    else:
      mv_list = [card for card in card_list if card["mv"] == mv]
      if len(mv_list) > 0:
        print("\t%s cards at mana value %s:" % (len(mv_list),mv))

    if len(mv_list) > 0:
      print(hrule)
      for card in mv_list:

        # Prepare the list of automatic tags that will be shown in the table
        pr_tags_dict = {category:tags for category, tags in card['auto_tags'].items() if category not in ["keywords","characteristics"]}
        pr_tags_list = list(itertools.chain(*list(pr_tags_dict.values()))) # Flatten the list of lists into a single list
        
        # Print the table content
        pr_tags_str = ", ".join([tag for tag in pr_tags_list if not tag.startswith((prefix_exc,prefix_ign,prefix_res))])
        pr_tags_str = (pr_tags_str[:75] + '(...)') if len(pr_tags_str) > 77 else pr_tags_str
        print(column_sizes.format(card['name'], card['mana_costs'], card['reason'],card['rank'] if card['rank'] != float('inf') else " (ILLEGAL)", pr_tags_str))
        
      print(hrule)

  # Print other data about the list

  console_message = "Other information about the list"
  print(''.center(len(console_message)+11, '*'))
  print(console_message.center(len(console_message)+10))
  print(''.center(len(console_message)+11, '*'))
  print("")

  ranks = [card['rank'] for card in card_list]
  list_median = int(statistics.median(ranks))

  print("{:<35} {:<25}".format("EDHrec rank median: ", str(list_median) + " (%s average)" % ("above" if list_median < pile_median else "below")))
  for status in lim_status:
    print("{:<35} {:<15}".format("Number of %s cards: " % status, lim_status[status]['count']))
  print("{:<35} {:<15}".format("Number of filler cards: ", filler_count))

  print("\nHard costs repartition:\n")
  for costs,number in current_costs.items():

    patterns = costs.split(',')
    patterns = [cost.strip() for cost in patterns if cost != '']

    if len(patterns) == 1:
      print("- %s %s with %s pattern" % (number,"cards" if number > 1 else "card",patterns[0]))
    elif len(patterns) == 2:
      print("- %s %s with %s or %s patterns" % (number,"cards" if number > 1 else "card",patterns[0],patterns[1]))
    else:
      print("- %s %s with %s, " % (number,"cards" if number > 1 else "card",patterns[0]), end="")
      print(", ".join(patterns[1:-1]),end="")
      print(" or %s patterns" % patterns[-1])

  all_tags = [tag for tags in [card['tags'] for card in card_list] for tag in tags]
  print("\nTheme tags repartition:\n")
  relevant_tags = [tag.strip() for tags in [tags.split(",") for tags in theme_data['tags'].keys() if tags != 'filler' and tags != 'restricted'] for tag in tags]
  if relevant_tags == []:
    print("- None")
  else:
    for tag in relevant_tags:
      print("- %s %s with the %s tag" % (all_tags.count(tag),"cards" if all_tags.count(tag) > 1 else "card", tag.upper()))

  print("\nGeneric tags repartition:\n")
  generic_tags = ['ramp','draw','removal','sweeper']
  for tag in generic_tags:
    print("- %s %s with the %s tag" % (all_tags.count(tag),"cards" if all_tags.count(tag) > 1 else "card", tag.upper()))

  # Generate the text file of the list if it is requested

  if time_it:
    answer = "No"
  else:
    answer = of.askYesNoQuestion("\nDo you want me to create a text file with the list in this directory? (Y/N)\n")
  
  if answer.startswith('Y'):
    filename = deck.lower() + "_" + inp_theme.lower().replace(" ","_") + "_" + str(date.today()) + ".txt"
    with open(filename, 'w+', encoding='utf-8') as f:
      for card in card_list:
        f.write("1 %s\n" % card['name'])
    print("As requested, a text file of the list has been saved with the name %s" % filename)

  print("\nEND OF CODE EXECUTION")
  if not time_it:
    input("Press ENTER to exit.")

# =================================================================== #
# =================================================================== #
#                          CALL MAIN FUNCTION                         #
# =================================================================== #
# =================================================================== #

if __name__ == "__main__":

  if time_it:

    import sys
    original_stdout = sys.stdout
    f = open(os.devnull, 'w')
    sys.stdout = f

    start = time.time()

    for i in range(time_it):
      main()

    elapsed_time = (time.time() - start)
    average_time =  elapsed_time/time_it
    sys.stdout = original_stdout

    print("Total execution time (%s): %s" % (time_it,elapsed_time))
    print("Average execution time: %s" % average_time)

  else:
    main()
