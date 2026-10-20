#!/usr/bin/python3
"""Curated, free desktop games for modest Linux Mint XFCE laptops.

Package IDs refer to Ubuntu/Debian APT packages, NEVER external downloads.
Installer input is game IDs, never shell commands or user-provided package names.
The catalogue favours older hardware, with optional marked 3D games.
"""

GAMES = (
    # Learning: good for older hardware.
    ('gcompris', 'GCompris', 'Learning', 'Reading, maths, memory and problem solving (larger download)', 'gcompris-qt'),
    ('tuxmath', 'Tux Maths', 'Learning', 'Arcade-style addition, subtraction and multiplication', 'tuxmath'),
    ('tuxtype', 'Tux Typing', 'Learning', 'Fun typing and keyboard practice', 'tuxtype'),
    ('kgeography', 'KGeography', 'Learning', 'Maps, countries, capitals and flags (adds KDE educational libraries)', 'kgeography'),
    # Creative: Minetest is heavier, but offline worlds work without server access.
    ('tuxpaint', 'Tux Paint', 'Creative', 'Draw, paint and explore colours', 'tuxpaint'),
    ('ktuberling', 'KTuberling', 'Creative', 'Build pictures from colourful objects (adds KDE libraries)', 'ktuberling'),
    ('minetest', 'Minetest (Luanti predecessor)', 'Creative', 'Minecraft-like offline worlds; heavier 3D game, try lowest graphics settings', 'minetest'),
    # Logic and memory.
    ('pingus', 'Pingus', 'Puzzles', 'Lemmings-style logic, planning and problem solving', 'pingus'),
    ('sudoku', 'Sudoku', 'Puzzles', 'Number-placement logic puzzles', 'gnome-sudoku'),
    ('frozenbubble', 'Frozen Bubble', 'Puzzles', 'Colour-matching and aiming puzzle game', 'frozen-bubble'),
    ('blinken', 'Blinken', 'Puzzles', 'Memory and pattern game, like Simon Says (adds KDE libraries)', 'blinken'),
    # Optional fun. Three-dimensional games may run slowly on Intel HD 3000.
    ('supertux', 'SuperTux', 'Just for fun', 'Lightweight 2D platform adventures', 'supertux'),
    ('supertuxkart', 'SuperTuxKart', 'Just for fun', '3D kart racing; large download and may be slow on older Intel graphics', 'supertuxkart'),
    ('extremetuxracer', 'Extreme Tux Racer', 'Just for fun', 'Slide down snowy slopes in 3D; reduce graphics quality if slow', 'extremetuxracer'),
    ('hedgewars', 'Hedgewars', 'Just for fun', 'Turn-based Worms-style strategy; larger download', 'hedgewars'),
)

BY_ID = {game[0]: game for game in GAMES}
assert len(BY_ID) == len(GAMES)
assert len({game[4] for game in GAMES}) == len(GAMES)


def validate_game_ids(value):
    """Return a deduplicated ordered tuple of selected approved game IDs.

    Fresh setup requests missing the optional games field remain compatible.
    Invalid types, IDs or duplicates are always rejected, before root actions.
    """
    if not isinstance(value, list) or len(value) > len(GAMES):
        raise ValueError('Invalid games selection. Select only the listed free games.')
    if any(type(game_id) is not str or game_id not in BY_ID for game_id in value):
        raise ValueError('One or more selected games are not in ParentPilot’s approved list.')
    if len(set(value)) != len(value):
        raise ValueError('Duplicate game selected.')
    return tuple(value)


def package_names(game_ids):
    return tuple(BY_ID[key][4] for key in validate_game_ids(list(game_ids)))


# Optional Linux desktop media players, kept separate from educational games.
# No third-party repository, Kodi add-on or streaming plugin is installed.
MEDIA_PLAYERS = (
    ('kodi', 'Kodi Media Centre', 'Media Players',
     'Play local films, cartoons and music; best suited to SD and 720p on older PCs', 'kodi'),
)
BY_MEDIA_ID = {player[0]: player for player in MEDIA_PLAYERS}
assert len(BY_MEDIA_ID) == len(MEDIA_PLAYERS)


def validate_media_ids(value):
    """Allow only named desktop APT media packages; default OFF."""
    if not isinstance(value, list) or len(value) > len(MEDIA_PLAYERS):
        raise ValueError('Invalid media player selection.')
    if any(type(media_id) is not str or media_id not in BY_MEDIA_ID for media_id in value):
        raise ValueError('Selected media player is not approved by ParentPilot.')
    if len(set(value)) != len(value):
        raise ValueError('Duplicate media player selected.')
    return tuple(value)
