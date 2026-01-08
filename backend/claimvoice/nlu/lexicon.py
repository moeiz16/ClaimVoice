"""Word lists for how callers describe a loss, in English and Canadian French.

One source for two readers: the value extractors (`nlu.extract`) build their patterns from these lists, and the
paraphrase generator (`nlu.corpus`) composes training sentences for the loss-type classifier from them. Lists are
written from claims-intake practice (first notice of loss forms, adjuster checklists, common causes of loss), not from
any held-out caller. A place ("the upstairs neighbour") is not a water source: the line asks what let go.
docs/NLU_CORPUS.md describes how they are used.
"""

from __future__ import annotations

LOSS_TYPES = ("collision", "hail", "wind", "water", "fire", "theft")
NONE = "none"  # not a description of a loss (a yes, a date, a policy number, a question, a generic "I need a claim")
LABELS = (*LOSS_TYPES, NONE)

# ------------------------------------------------------------------ vehicles and their parts

VEHICLES_EN = (
    "car", "truck", "pickup", "pickup truck", "SUV", "van", "minivan", "jeep", "crossover", "hatchback", "sedan",
    "Civic", "Corolla", "F-150", "RAV4", "Camry", "CR-V", "Tacoma", "Silverado", "Outback", "Escape", "Model 3",
    "Ram", "Sierra", "Elantra", "Mazda", "Subaru", "motorcycle", "trailer", "camper",
)  # fmt: skip
VEHICLES_FR = (
    "voiture", "auto", "char", "camion", "pick-up", "camionnette", "VUS", "fourgonnette", "minifourgonnette", "jeep",
    "Civic", "Corolla", "Mazda 3", "RAV4", "moto", "remorque", "roulotte",
)  # fmt: skip
OTHER_VEHICLES_EN = (
    "a pickup", "a truck", "a car", "another car", "a van", "a delivery van", "a delivery truck", "a semi", "a cab",
    "a taxi", "a city bus", "a bus", "an SUV", "a minivan", "a snowplow", "a garbage truck", "a cement truck",
    "a tow truck", "a cyclist", "a motorcycle", "a school bus", "a work truck", "an Uber", "a jeep",
    "this guy", "a guy", "this lady", "a woman", "a man", "an older gentleman", "a kid", "a teenager", "a driver",
    "another driver", "someone", "somebody", "the car behind me", "the guy behind me", "the truck in front of me",
    "a young driver", "my neighbour", "a contractor's truck", "a rental car",
)  # fmt: skip
OTHER_VEHICLES_FR = (
    "un camion", "un pick-up", "une voiture", "une auto", "un char", "un autre char", "un camion de livraison",
    "un taxi", "un autobus", "un VUS", "une fourgonnette", "une déneigeuse", "un camion de vidanges", "un remorqueur",
    "un cycliste", "une moto", "un gars", "une madame", "un monsieur", "un jeune", "quelqu'un", "un conducteur",
    "une conductrice", "l'auto derrière moi", "le camion en avant de moi", "un voisin", "un camion de la ville",
)  # fmt: skip

VEHICLE_PARTS_EN = (
    "rear bumper", "front bumper", "bumper", "trunk", "tailgate", "hood", "driver's door", "driver door",
    "passenger door", "rear door", "back door", "door", "front fender", "rear fender", "fender", "quarter panel",
    "windshield", "rear window", "side window", "tail light", "taillight", "headlight", "side mirror",
    "driver side mirror", "passenger mirror", "mirror", "grille", "wheel", "rim", "tire", "hubcap", "axle",
    "radiator", "rocker panel", "running board", "hitch", "roof rack", "sunroof", "undercarriage", "frame",
    "back end", "front end", "rear end", "side", "driver's side", "passenger side",
)  # fmt: skip
VEHICLE_PARTS_FR = (
    "pare-chocs arrière", "pare-chocs avant", "pare-chocs", "coffre", "hayon", "capot", "portière du conducteur",
    "portière arrière", "portière", "porte arrière", "porte", "aile avant", "aile arrière", "aile", "pare-brise",
    "lunette arrière", "vitre", "feu arrière", "phare", "rétroviseur", "miroir", "grille", "roue", "jante", "pneu",
    "radiateur", "bas de caisse", "toit ouvrant", "châssis", "l'arrière", "l'avant", "le devant", "le côté",
    "côté conducteur", "côté passager",
)  # fmt: skip

# ------------------------------------------------------------------ the home

HOME_PARTS_EN = (
    "roof", "shingles", "siding", "vinyl siding", "stucco", "skylight", "window", "front window", "patio door",
    "fence", "garage door", "eavestrough", "eavestroughs", "gutter", "gutters", "downspout", "soffit", "fascia",
    "ceiling", "drywall", "wall", "floor", "hardwood", "carpet", "laminate", "subfloor", "baseboards", "furnace",
    "deck", "shed", "chimney", "flashing", "vent", "awning", "pergola", "gazebo", "satellite dish", "trusses",
    "insulation", "foundation", "cabinets", "countertop",
)  # fmt: skip
HOME_PARTS_FR = (
    "toit", "toiture", "bardeaux", "revêtement", "parement", "crépi", "puits de lumière", "lucarne", "fenêtre",
    "porte-patio", "clôture", "porte de garage", "gouttière", "gouttières", "descente pluviale", "soffite", "fascia",
    "plafond", "gypse", "mur", "plancher", "bois franc", "tapis", "sous-plancher", "plinthes", "fournaise",
    "galerie", "balcon", "patio", "cabanon", "cheminée", "solin", "auvent", "isolant", "fondation", "armoires",
    "comptoir",
)  # fmt: skip

ROOMS_EN = (
    "kitchen", "basement", "living room", "family room", "rec room", "laundry room", "laundry", "bedroom",
    "master bedroom", "spare room", "kids' room", "bathroom", "ensuite", "powder room", "garage", "dining room",
    "hallway", "office", "den", "attic", "crawl space", "mudroom", "entryway", "furnace room", "utility room",
    "storage room", "closet", "pantry", "sunroom", "stairwell",
)  # fmt: skip
ROOMS_FR = (
    "cuisine", "sous-sol", "salon", "salle familiale", "salle de jeux", "buanderie", "chambre", "chambre principale",
    "chambre d'amis", "salle de bain", "salle de bains", "salle d'eau", "garage", "salle à manger", "corridor",
    "couloir", "bureau", "grenier", "vide sanitaire", "vestibule", "entrée", "salle mécanique", "rangement",
    "garde-robe", "solarium", "cage d'escalier",
)  # fmt: skip

# ------------------------------------------------------------------ water

# (phrase, water_source choice). Order matters only for the generator; the extractor checks every phrase.
WATER_SOURCES_EN: tuple[tuple[str, str], ...] = (
    ("burst pipe", "burst_pipe"), ("frozen pipe", "burst_pipe"), ("broken pipe", "burst_pipe"),
    ("split pipe", "burst_pipe"), ("cracked pipe", "burst_pipe"), ("pipe burst", "burst_pipe"),
    ("pipe froze", "burst_pipe"), ("pipe under the sink", "burst_pipe"), ("supply line", "burst_pipe"),
    ("water line", "burst_pipe"), ("pipe in the wall", "burst_pipe"), ("plumbing", "burst_pipe"),
    ("sewer", "sewer_backup"), ("sewage", "sewer_backup"), ("floor drain", "sewer_backup"), ("drain", "sewer_backup"),
    ("backwater valve", "sewer_backup"), ("sump pump", "sewer_backup"), ("sump", "sewer_backup"),
    ("river", "overland"), ("creek", "overland"), ("overland", "overland"), ("surface water", "overland"),
    ("flash flood", "overland"), ("snow melt", "overland"), ("melting snow", "overland"), ("runoff", "overland"),
    ("window well", "overland"), ("rain came in under", "overland"), ("groundwater", "overland"),
    ("roof", "roof"), ("ice dam", "roof"), ("attic", "roof"), ("flashing", "roof"), ("skylight", "roof"),
    ("chimney", "roof"),
    ("washer", "appliance"), ("washing machine", "appliance"), ("dishwasher", "appliance"),
    ("water heater", "appliance"), ("hot water tank", "appliance"), ("hot water heater", "appliance"),
    ("fridge", "appliance"), ("refrigerator", "appliance"), ("ice maker", "appliance"), ("humidifier", "appliance"),
    ("water softener", "appliance"), ("furnace", "appliance"), ("boiler", "appliance"), ("aquarium", "other"),
    ("toilet", "other"), ("bathtub", "other"), ("tub", "other"), ("shower", "other"), ("sink", "other"),
)  # fmt: skip
WATER_SOURCES_FR: tuple[tuple[str, str], ...] = (
    ("tuyau éclaté", "burst_pipe"), ("tuyau gelé", "burst_pipe"), ("tuyau fendu", "burst_pipe"),
    ("tuyau brisé", "burst_pipe"), ("tuyau percé", "burst_pipe"), ("conduite", "burst_pipe"),
    ("tuyauterie", "burst_pipe"), ("plomberie", "burst_pipe"), ("tuyau", "burst_pipe"),
    ("égout", "sewer_backup"), ("refoulement", "sewer_backup"), ("refoulé", "sewer_backup"), ("drain", "sewer_backup"),
    ("clapet", "sewer_backup"), ("pompe de puisard", "sewer_backup"), ("puisard", "sewer_backup"),
    ("rivière", "overland"), ("crue", "overland"), ("ruisseau", "overland"), ("fonte des neiges", "overland"),
    ("eaux de surface", "overland"), ("margelle", "overland"), ("nappe phréatique", "overland"),
    ("toit", "roof"), ("toiture", "roof"), ("barrage de glace", "roof"), ("digue de glace", "roof"),
    ("grenier", "roof"), ("solin", "roof"), ("puits de lumière", "roof"),
    ("laveuse", "appliance"), ("machine à laver", "appliance"), ("lave-vaisselle", "appliance"),
    ("chauffe-eau", "appliance"), ("réservoir d'eau chaude", "appliance"), ("frigo", "appliance"),
    ("réfrigérateur", "appliance"), ("humidificateur", "appliance"), ("fournaise", "appliance"),
    ("toilette", "other"), ("bain", "other"), ("baignoire", "other"), ("douche", "other"), ("évier", "other"),
    ("lavabo", "other"),
)  # fmt: skip
WATER_VERBS_EN = (
    "dripping", "leaking", "coming in", "coming down", "pouring", "running", "seeping", "gushing", "trickling",
    "pooling", "spraying", "flooding", "soaking", "streaming",
)  # fmt: skip
WATER_VERBS_FR = (
    "coule", "dégoutte", "s'infiltre", "rentre", "entre", "gicle", "suinte", "déborde", "s'accumule", "ruisselle",
)  # fmt: skip

# ------------------------------------------------------------------ causes of loss (for the generator)

WIND_CAUSES_EN = (
    "the wind", "the windstorm", "the storm", "that storm", "the Chinook", "a big gust", "the gusts", "a microburst",
    "the high winds", "the wind last night", "the storm last night", "a gust of wind", "the blizzard", "the gale",
    "a downburst", "the squall", "that windstorm", "the big blow",
)  # fmt: skip
WIND_CAUSES_FR = (
    "le vent", "les grands vents", "la tempête", "la tempête de vent", "une bourrasque", "les rafales", "une rafale",
    "le vent de cette nuit", "la tempête d'hier", "un coup de vent", "la tornade", "le blizzard",
)  # fmt: skip
WIND_VERBS_EN = (
    "ripped", "tore", "blew", "knocked down", "took", "lifted", "flattened", "toppled", "snapped", "pulled down",
    "brought down", "tipped over", "threw", "yanked", "sheared off", "blew over", "wrecked",
)  # fmt: skip
WIND_TARGETS_EN = (
    "shingles off the roof", "a bunch of shingles off", "half the shingles", "the fence", "the side fence",
    "the gutter off", "the eavestroughs off the house", "the siding off the back", "the shed over",
    "a tree onto the house",
    "a heavy limb onto the roof", "the soffit off", "part of the roof", "the satellite dish off", "the gazebo",
    "the patio umbrella through the window", "the trampoline over the fence", "the garage door in", "the flashing off",
    "the vents off the roof", "the awning", "a panel of fence", "the neighbour's tree onto our garage",
)  # fmt: skip
WIND_VERBS_FR = (
    "a arraché", "a emporté", "a renversé", "a cassé", "a soulevé", "a jeté par terre", "a défait", "a fait tomber",
    "a brisé", "a plié",
)  # fmt: skip
WIND_TARGETS_FR = (
    "les bardeaux", "des bardeaux sur le toit", "la clôture", "la gouttière", "le revêtement", "un arbre sur la maison",
    "une grosse branche sur le toit", "le cabanon", "une partie de la toiture", "l'auvent", "le soffite",
    "la porte de garage", "la clôture du voisin", "l'antenne",
)  # fmt: skip
WIND_FALLS_EN = (
    "a tree fell on the house", "a branch fell on the roof", "our fence blew over", "a tree came down on the garage",
    "the neighbour's tree fell on our roof", "a limb came through the bedroom window", "the shed blew into the fence",
    "a limb snapped and hit the car", "shingles are all over the yard", "part of the roof blew off",
)  # fmt: skip
WIND_FALLS_FR = (
    "un arbre est tombé sur la maison", "une branche est tombée sur le toit", "la clôture est tombée avec le vent",
    "des bardeaux sont partis au vent", "un morceau du toit est parti", "l'arbre du voisin est tombé sur le garage",
)  # fmt: skip

HAIL_CAUSES_EN = (
    "the hail", "hail", "the hailstorm", "a hailstorm", "that hail", "golf-ball-sized hail",
    "hail the size of golf balls",
    "the hail last summer", "the storm with the hail", "the hail on Tuesday", "big hailstones", "ice pellets",
    "hailstones the size of marbles", "loonie-sized hail", "pea-sized hail", "hail as big as toonies",
)  # fmt: skip
HAIL_VERBS_EN = (
    "dented", "cracked", "smashed", "pounded", "shredded", "pitted", "destroyed", "beat up", "pockmarked", "broke",
    "punched holes in", "chipped", "wrecked", "damaged",
)  # fmt: skip
HAIL_TARGETS_EN = (
    "my car", "the hood", "the roof", "the siding", "my windshield", "the skylights", "the vinyl siding", "the deck",
    "the truck", "the shingles", "the eavestroughs", "the gutters", "the screens", "the greenhouse", "the trunk",
)  # fmt: skip
HAIL_CAUSES_FR = (
    "la grêle", "la tempête de grêle", "des grêlons", "des grêlons gros comme des balles de golf",
    "la grêle de cet été",
)  # fmt: skip
HAIL_VERBS_FR = ("a bosselé", "a fissuré", "a cassé", "a endommagé", "a criblé", "a abîmé", "a percé", "a brisé")
HAIL_TARGETS_FR = (
    "mon auto", "le toit", "le pare-brise", "le revêtement", "le capot", "les bardeaux", "les gouttières",
    "mon char", "le puits de lumière", "la serre",
)  # fmt: skip

FIRE_EVENTS_EN = (
    "a fire started", "we had a fire", "there was a small fire", "a grease fire started", "something caught fire",
    "there was an electrical fire", "we had a chimney fire", "the dryer caught fire", "the stove caught fire",
    "the barbecue caught fire", "a candle started a fire", "the toaster caught fire", "an outlet caught fire",
    "the microwave caught fire", "a pot caught fire", "a heater started a fire", "a cigarette started a fire",
    "the furnace caught fire", "the deck caught fire", "we had a kitchen fire",
    "a fire broke out", "a fire in the wall", "the fireplace set the mantel on fire",
)  # fmt: skip
FIRE_AFTER_EN = (
    "it's out now", "the fire department put it out", "everything smells like smoke", "the walls are black with soot",
    "there's smoke damage everywhere", "the cabinets are scorched", "the ceiling is charred", "the fire's out",
    "we put it out with an extinguisher", "the firefighters came", "the whole room is burned", "it melted the counter",
)  # fmt: skip
FIRE_EVENTS_FR = (
    "on a eu un feu", "un feu a pris", "il y a eu un petit feu", "un feu de cuisine", "un feu de friture",
    "la sécheuse a pris feu", "la cuisinière a pris feu", "le barbecue a pris feu", "une chandelle a mis le feu",
    "un feu électrique", "un feu de cheminée", "une prise a pris feu", "il y a eu un incendie", "le feu a pris",
    "le grille-pain a pris feu", "une chaufferette a mis le feu",
)  # fmt: skip
FIRE_AFTER_FR = (
    "c'est éteint", "les pompiers l'ont éteint", "ça sent la fumée partout dans la maison",
    "les murs sont noirs de suie",
    "il y a des dommages de fumée", "les armoires sont brûlées", "le plafond est noirci", "le feu est éteint",
    "on l'a éteint avec l'extincteur",
)  # fmt: skip

THEFT_VERBS_EN = (
    "stole", "took", "swiped", "made off with", "walked off with", "grabbed", "lifted", "cleaned out", "sawed off",
    "cut off", "drove off with", "helped themselves to", "got away with",
)  # fmt: skip
THEFT_ITEMS_EN = (
    "my car", "my truck", "my bike", "the catalytic converter", "my tools",
    "my laptop", "my purse", "the snowblower", "my tires", "the TV", "my jewelry", "my wallet", "the packages",
    "my trailer", "the generator", "my golf clubs", "the lawnmower", "my wheels", "my stereo", "the mail",
    "my camera", "my motorcycle", "the kids' bikes", "the power tools", "my work tools", "my rims",
)  # fmt: skip
THEFT_ENTRY_EN = (
    "broke into", "broke in to", "pried open", "jimmied", "smashed the window of", "kicked in the door of",
    "forced the lock on", "cut the lock on", "broke the window of",
)  # fmt: skip
THEFT_PLACES_EN = (
    "the garage", "the house", "my car", "the shed", "our place", "the truck", "the storage locker", "the basement",
    "the van", "my apartment", "the cottage", "the camper",
)  # fmt: skip
THEFT_PASSIVE_EN = (
    "my car is gone", "my truck was stolen", "our house got broken into", "the shed was cleaned out",
    "my car isn't where I parked it", "we were robbed", "we got robbed", "somebody broke in", "there was a break-in",
    "we were burglarized", "my bike got stolen", "our garage was broken into", "my car got broken into",
    "my plates were stolen", "we had a burglary",
)  # fmt: skip
THEFT_FR = (
    "on m'a volé {item}", "quelqu'un a volé {item}", "quelqu'un a pris {item}", "ils ont pris {item}",
    "ils sont partis avec {item}", "on s'est fait voler {item}", "{item_subj} a été volé", "{item_subj} a disparu",
)  # fmt: skip
THEFT_ITEMS_FR = (
    "mon auto", "mon char", "mon vélo", "mes outils", "la souffleuse", "mon portable", "mes pneus", "la télé",
    "mes bijoux", "mon portefeuille", "les colis", "ma remorque", "la génératrice", "le convertisseur catalytique",
    "mon camion", "ma moto", "mes bâtons de golf",
)  # fmt: skip
THEFT_ENTRY_FR = (
    "on s'est fait cambrioler", "quelqu'un est entré chez nous", "on est entré par effraction", "il y a eu un vol",
    "ils ont forcé la porte", "ils ont fracassé une fenêtre", "quelqu'un a forcé le cabanon",
    "on a forcé la serrure du garage", "ils ont brisé la vitre de l'auto", "on a été cambriolés",
)  # fmt: skip

COLLISION_VERBS_EN = (
    "clipped", "rear-ended", "hit", "sideswiped", "backed into", "ran into", "smashed into", "slammed into",
    "bumped", "tapped", "t-boned", "plowed into", "nicked", "scraped", "dinged", "crunched", "rammed", "struck",
    "swiped", "creamed", "nailed", "hit the side of", "drove into", "pulled out in front of me and hit",
    "cut me off and hit", "ran a red and hit", "merged into", "reversed into",
)  # fmt: skip
COLLISION_OBJECTS_EN = (
    "my car", "my truck", "the side of my car", "my bumper", "my SUV", "my van", "the back of my car",
    "my parked car", "my wife's car", "the front of my truck", "my door", "me", "us", "the passenger side",
    "my mirror", "my rear end",
)  # fmt: skip
SINGLE_VEHICLE_EN = (
    "I hit a deer", "I hit a moose", "I slid into a pole", "I went into the ditch", "I backed into a post",
    "I lost control on the ice", "I swerved to miss a deer and hit a tree", "I scraped a pillar in the parkade",
    "I slid through the intersection and hit the curb", "I rear-ended someone", "I backed into a parked car",
    "I hit a pothole and blew a tire", "I hit the guardrail", "I clipped the garage door backing out",
    "I spun out and hit the median", "my car slid into a light post", "I bumped a bollard in the drive-thru",
    "I ran into a snowbank and hit a sign",
)  # fmt: skip
COLLISION_PLACES_EN = (
    "", " on Deerfoot", " at the lights", " in a parking lot", " merging onto the highway", " at the intersection",
    " in the Costco lot", " on my way to work", " on Highway 2", " in the drive-thru", " on the ring road",
    " at a four-way stop", " backing out of my driveway", " in the school zone", " on Federal", " on I-25",
    " at the mall", " in a roundabout", " on Crowchild", " in the underground parking",
)  # fmt: skip
COLLISION_VERBS_FR = (
    "a accroché", "m'a rentré dedans", "a embouti", "a frappé", "a heurté", "a percuté", "a reculé dans",
    "a éraflé", "a cogné", "a accroché le côté de", "a tamponné", "est rentré dans", "a défoncé", "a égratigné",
)  # fmt: skip
COLLISION_OBJECTS_FR = (
    "ma voiture", "mon char", "mon auto", "mon camion", "ma portière", "le côté de mon auto", "l'arrière de mon auto",
    "mon pare-chocs", "ma voiture stationnée",
)  # fmt: skip
SINGLE_VEHICLE_FR = (
    "un chevreuil a sauté devant l'auto", "j'ai frappé un orignal", "j'ai glissé dans le fossé",
    "j'ai perdu le contrôle sur la glace",
    "j'ai reculé dans un poteau", "j'ai embouti l'auto en avant", "j'ai glissé dans un banc de neige",
    "j'ai accroché un pilier dans le stationnement", "je suis rentré dans une clôture", "j'ai fait un tête-à-queue",
)  # fmt: skip
COLLISION_PLACES_FR = (
    "", " sur la 40", " à un feu rouge", " dans le stationnement du IGA", " sur le boulevard",
    " en sortant de l'autoroute",
    " sur la 20", " au coin de la rue", " en reculant", " dans un rond-point", " sur le pont", " sur la rue Sherbrooke",
)  # fmt: skip

# ------------------------------------------------------------------ people and hedges

HEDGES_EN = (
    "", "I think ", "um, ", "uh, ", "so basically ", "I guess ", "it looks like ", "I'm pretty sure ", "so ",
    "well, ", "okay so ", "honestly ", "I believe ", "so yeah, ",
)  # fmt: skip
HEDGES_FR = ("", "je pense que ", "euh, ", "ben ", "en fait ", "on dirait que ", "je crois que ", "bon, ", "fait que ")
OPENERS_EN = (
    "", "Hi, ", "Hello, ", "Hey, ", "Good morning, ", "Morning. ", "Hi there, ", "Yeah hi, ", "Um, hi, ",
    "Hi, I need to report a claim. ", "Hi, I'm calling because ", "Hello, I need to open a claim, ", "Hey there. ",
    "Good afternoon. ", "Hi, sorry, ", "Hi, I'm not sure who to call, but ", "Hello? Hi. ",
)  # fmt: skip
OPENERS_FR = (
    "", "Bonjour, ", "Allô, ", "Oui bonjour, ", "Bonjour. ", "Allô, bonjour. ", "Bonjour, j'appelle parce que ",
    "Bonjour, je dois faire une réclamation. ", "Salut, ", "Bonjour madame, ",
)  # fmt: skip
TAILS_EN = (
    "", " this morning", " last night", " yesterday", ", I'm a bit shaken", ", it's pretty bad", " about an hour ago",
    ", what a mess", " over the weekend", " a couple of days ago",
    ", I don't know what to do", " while we were at work",
)  # fmt: skip
TAILS_FR = (
    "", " ce matin", " cette nuit", " hier", " en revenant du travail", ", je suis un peu sous le choc",
    ", c'est pas beau",
    " pendant la fin de semaine", " il y a une heure", ", quel dégât",
)  # fmt: skip

# ------------------------------------------------------------------ injuries

BODY_EN = (
    "neck", "back", "lower back", "head", "arm", "leg", "shoulder", "knee", "wrist", "chest", "hand", "hip", "ankle",
    "ribs", "collarbone", "face", "nose",
)  # fmt: skip
BODY_FR = (
    "cou", "dos", "bas du dos", "tête", "bras", "jambe", "épaule", "genou", "poignet", "poitrine", "main", "hanche",
    "cheville", "côtes", "visage", "nez",
)  # fmt: skip
INJURY_WORDS_EN = (
    "sore", "stiff", "hurts", "hurting", "aching", "bruised", "cut", "sprained", "throbbing", "banged up",
    "bleeding", "swollen", "tender", "pulled",
)  # fmt: skip
