# Copyright (c) 2010-2012 Lazy 8 Studios, LLC.
# All rights reserved.
from front import Constants, debug
from front.tools import replay_game

class StoryBeats(object):
    # An adhoc beat that is run before AT_LANDER to emulate completing the tutorials before
    # creating any targets.
    class COMPLETE_TUTORIALS(replay_game.ReplayGameBeat):
        CLIENT_PROGRESS = Constants.SIMULATOR_PROGRESS_KEYS

    class AT_LANDER(replay_game.ReplayGameBeat):
        ID_SPECIES = ['SPC_LANDER01']
    AT_LANDER.before_beat_run_beat(COMPLETE_TUTORIALS)

    class ID_5_SPECIES(replay_game.ReplayGameBeat):
        ID_SPECIES = debug.rects.PLANTS[0:5]

    class AT_ARTIFACT01(replay_game.ReplayGameBeat):
        ID_SPECIES = ['SPC_ARTIFACT01']

    class AT_ARTIFACT01_CLOSEUP(replay_game.ReplayGameBeat):
        ID_SPECIES = ['SPC_ARTIFACT01']

    class JUST_INSIDE_SANDBOX(replay_game.ReplayGameBeat):
        CREATE_NEXT_TARGETS = 2

    class ID_10_SPECIES(replay_game.ReplayGameBeat):
        ID_SPECIES = debug.rects.PLANTS[5:11]

    class AT_STUCK_ROVER(replay_game.ReplayGameBeat):
        ID_SPECIES = ['SPC_ROVER_DISASSEMBLED']

    class AT_AUDIO_TUTORIAL01_PINPOINT(replay_game.ReplayGameBeat):
        ID_SPECIES = ['SPC_ANIMAL001']

    class AT_AUDIO_MYSTERY01_PINPOINT(replay_game.ReplayGameBeat):
        ID_SPECIES = ['SPC_UNKNOWN_ORIGIN02']

    class AT_GPS(replay_game.ReplayGameBeat):
        ID_SPECIES      = ['SPC_MANMADE005']
        MESSAGES_UNLOCK = ['MSG_ENCRYPTION01']

    class AT_CENTRAL_MONUMENT(replay_game.ReplayGameBeat):
        ID_SPECIES = ['SPC_UNKNOWN_ORIGIN08']

    class AT_OBELISK02_PINPOINT(replay_game.ReplayGameBeat):
        ID_SPECIES = ['SPC_UNKNOWN_ORIGIN02_SUB01']

    class AT_RUINS01(replay_game.ReplayGameBeat):
        ID_SPECIES = ['SPC_UNKNOWN_ORIGIN09']

    class AT_RUINS02(replay_game.ReplayGameBeat):
        ID_SPECIES = ['SPC_UNKNOWN_ORIGIN09']

    class AT_RUINS03(replay_game.ReplayGameBeat):
        ID_SPECIES = ['SPC_UNKNOWN_ORIGIN09']

    class AT_RUINS_SIGNAL(replay_game.ReplayGameBeat):
        ID_SPECIES = ['SPC_UNKNOWN_ORIGIN10']

    class AT_OBELISK03_PINPOINT(replay_game.ReplayGameBeat):
        ID_SPECIES = ['SPC_UNKNOWN_ORIGIN02_SUB02']

    class AT_OBELISK04_PINPOINT(replay_game.ReplayGameBeat):
        ID_SPECIES = ['SPC_UNKNOWN_ORIGIN02_SUB03']

    class AT_CODED_LOC(replay_game.ReplayGameBeat):
        ID_SPECIES = ['SPC_MANMADE006']

    class TOWARD_TURING_ROVER_02(replay_game.ReplayGameBeat):
        MESSAGES_UNLOCK = ['MSG_ENCRYPTION02']

    class TOWARD_TURING_ROVER_04(replay_game.ReplayGameBeat):
        MESSAGES_FORWARD  = [('MSG_ENCRYPTION02', 'ENKI')]

    class AT_TURING_ROVER(replay_game.ReplayGameBeat):
        ID_SPECIES = ['SPC_MANMADE007']
        MESSAGES_UNLOCK = ['MSG_ENKI02d']

    class TOWARD_OBELISK05_02(replay_game.ReplayGameBeat):
        MESSAGES_UNLOCK = ['MSG_BACKb']

    class AT_OBELISK05_PINPOINT(replay_game.ReplayGameBeat):
        ID_SPECIES = ['SPC_UNKNOWN_ORIGIN02_SUB04']

    class AT_OBELISK06_PINPOINT(replay_game.ReplayGameBeat):
        ID_SPECIES = ['SPC_UNKNOWN_ORIGIN02_SUB05']

    class TOWARD_CENTRAL_MONUMENT_PLAYBACK02(replay_game.ReplayGameBeat):
        MESSAGES_UNLOCK = ['MSG_OBELISK06b']

    class TOWARD_MISSING_ROVER03(replay_game.ReplayGameBeat):
        CREATE_NEXT_TARGETS = 2

    class AFTER_MISSING_ROVER01(replay_game.ReplayGameBeat):
        pass

    class AFTER_MISSING_ROVER02(replay_game.ReplayGameBeat):
        BEAT_ARRIVAL_DELTA = 90000
        RENDER_ADHOC_TARGET = True
    AFTER_MISSING_ROVER01.after_beat_run_beat(AFTER_MISSING_ROVER02)

    class AFTER_MISSING_ROVER03(replay_game.ReplayGameBeat):
        BEAT_ARRIVAL_DELTA = 600
        MESSAGES_UNLOCK = ['MSG_LASTTHINGa']
    AFTER_MISSING_ROVER02.after_beat_run_beat(AFTER_MISSING_ROVER03)

    class AFTER_MISSING_ROVER04(replay_game.ReplayGameBeat):
        BEAT_ARRIVAL_DELTA = 691200
        ID_SPECIES = ['SPC_PLANT65535']
    AFTER_MISSING_ROVER03.after_beat_run_beat(AFTER_MISSING_ROVER04)

    class SCI_FIND_COMMON_FIRST_TAGS(replay_game.ReplayGameBeat):
        ID_SPECIES = ['SPC_PLANT021_SUB04', 'SPC_PLANT024_SUB04', 'SPC_PLANT65535']

    class SCI_FIND_COMMON_SECOND_TAGS(replay_game.ReplayGameBeat):
        ID_SPECIES = ['SPC_PLANT021_SUB04', 'SPC_PLANT024_SUB04']

    class SCI_FIND_COMMONb(replay_game.ReplayGameBeat):
        ID_SPECIES = ['SPC_PLANT024_SUB04']

    class SCI_FIND_COMMONa(replay_game.ReplayGameBeat):
        ID_SPECIES = ['SPC_PLANT021_SUB04']
        
    class ID_15_SPECIES(replay_game.ReplayGameBeat):
        ID_SPECIES = ['SPC_PLANT012']

    class ID_GORDY_TREE_01(replay_game.ReplayGameBeat):
        ID_SPECIES = ['SPC_PLANT032']
    
    class ID_GORDY_TREE_02(replay_game.ReplayGameBeat):
        ID_SPECIES = ['SPC_PLANT032']
    
    class ID_GORDY_TREE_03(replay_game.ReplayGameBeat):
        ID_SPECIES = ['SPC_PLANT032']

    class ID_GORDY_TREE_YOUNG(replay_game.ReplayGameBeat):
        ID_SPECIES = ['SPC_PLANT032_SUB01']

    class ID_GORDY_TREE_DEAD(replay_game.ReplayGameBeat):
        ID_SPECIES = ['SPC_PLANT032_SUB02']

    class ID_BRISTLETONGUE_VARIANT(replay_game.ReplayGameBeat):
        ID_SPECIES = ['SPC_ANIMAL006']
    
    class ID_THIRD_CNIDERIA(replay_game.ReplayGameBeat):
        ID_SPECIES = ['SPC_PLANT034']
    
    class ID_STARSPORE_OPEN_CLOSED_01(replay_game.ReplayGameBeat):
        ID_SPECIES = ['SPC_PLANT028', 'SPC_PLANT028_SUB03']
    
    class ID_STARSPORE_OPEN_CLOSED_02(replay_game.ReplayGameBeat):
        ID_SPECIES = ['SPC_PLANT028', 'SPC_PLANT028_SUB03']
    
    class ID_BIOLUMINESCENCE_DAY(replay_game.ReplayGameBeat):
        ID_SPECIES = ['SPC_PLANT015', 'SPC_PLANT022', 'SPC_PLANT031']
    
    class ID_BIOLUMINESCENCE_NIGHT_01(replay_game.ReplayGameBeat):
        ID_SPECIES = ['SPC_PLANT015_SUB05', 'SPC_PLANT022_SUB05', 'SPC_PLANT031_SUB05']

    class ID_BIOLUMINESCENCE_NIGHT_02(replay_game.ReplayGameBeat):
        ID_SPECIES = ['SPC_PLANT015_SUB05', 'SPC_PLANT022_SUB05', 'SPC_PLANT031_SUB05']
            
    class ID_SAIL_FLYER_01(replay_game.ReplayGameBeat):
        ID_SPECIES = ['SPC_ANIMAL004']
    
    class ID_SAIL_FLYER_02(replay_game.ReplayGameBeat):
        ID_SPECIES = ['SPC_ANIMAL004']
    
    class ID_SAIL_FLYER_03(replay_game.ReplayGameBeat):
        ID_SPECIES = ['SPC_ANIMAL004']

    class OUTSIDE_AUDIO_MYSTERY07_ZONE(replay_game.ReplayGameBeat):
        ID_SPECIES = ['SPC_PLANT014', 'SPC_PLANT014_SUB04']

    class AT_AUDIO_MYSTERY07(replay_game.ReplayGameBeat):
        ID_SPECIES = ['SPC_PLANT014_SUB04']


def routes():
    return [debug.routes.struct(debug.routes.FASTEST_STORY_ROVER1),
            debug.routes.struct(debug.routes.FASTEST_STORY_ROVER2),
            debug.routes.struct(debug.routes.FASTEST_STORY_ROVER3)]

def beats():
    return [StoryBeats]
