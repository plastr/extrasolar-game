// Copyright (c) 2010-2012 Lazy 8 Studios, LLC.
// All rights reserved.
// ce4.mission.callbacks contains the Mission interaction code.
goog.provide("ce4.mission.callbacks");

// TODO: Circular dependency between ce4.mission.callbacks and ce4.ui..
// goog.require('ce4.ui');
// goog.require('ce4.ui.map');

ce4.mission.callbacks.get_first_incomplete_leaf = function() {
    var missions = ce4.gamestate.user.notdone_missions("root");
    if (missions && missions[0]) {
        return missions[0].get_first_incomplete_part();
    } else {
        return null;
    }
};

ce4.mission.callbacks.load_page = function (tag) {
    var first = ce4.mission.callbacks.get_first_incomplete_leaf();
    if (first) {
        first.get_hook('load')(first, tag);
    }
};

ce4.mission.callbacks.unload_page = function (tag) {
    var first = ce4.mission.callbacks.get_first_incomplete_leaf();
    if (first) {
        first.get_hook('unload')(first, tag);
    }
};

ce4.mission.callbacks.wizard_hook = function(step, target, wizard) {
    var first = ce4.mission.callbacks.get_first_incomplete_leaf();
    if (first) {
        first.get_hook('wizard')(first, step, target, wizard);
    }
};

ce4.mission.callbacks.get_hook = function(mission_definition, hookname) {
    var mc = ce4.mission.callbacks.code[mission_definition];
    if (mc) {
        var hook = mc[hookname];
        if (hook) {
            return hook;
        }
    }
    return function() {};
};

ce4.mission.callbacks.code = {
    MIS_TUT01a: {
        name: "MIS_TUT01a",
        load: function(mission, tag) 
        {
            if (tag === ce4.ui.LEAFLET) 
            {
                ce4.gamestate.user.tutorial.begin(ce4.tutorial.ids.TUT02, {mission: mission});
            }
        },
        unload: function(mission, tag) 
        {

            if (tag === ce4.ui.LEAFLET) 
            {
                ce4.gamestate.user.tutorial.abort(ce4.tutorial.ids.TUT02, {});
            }
        },
        wizard: function(mission, step, target_struct, wizard) 
        {
            if(step === 1) 
            {
                ce4.gamestate.user.tutorial.advance(ce4.tutorial.ids.TUT02, 'tutorial02-step01',  {mission: mission, wizard: wizard, target_struct: target_struct});
            } 
            else if (step === 2) 
            {
                ce4.gamestate.user.tutorial.advance(ce4.tutorial.ids.TUT02, 'tutorial02-step02',  {wizard: wizard});
            }
        },
        done: function() {
            if (ce4.ui.is_current_page_name(ce4.ui.LEAFLET)) {
                ce4.gamestate.user.tutorial.advance(ce4.tutorial.ids.TUT02, 'tutorial02-step03',  {});
            }
        }
    },

    MIS_MONUMENT_PLAYBACKa: {
        status: function() {
            // We need to track (a) how many obelisk sounds have been found and (b) whether or not
            // the corresponding obelisk has also been tagged.
            // Loop over all processed picture targets to see if any of these sounds are attached.
            var target_sounds  = ['SND_AUDIO_MYSTERY01', 'SND_AUDIO_MYSTERY02', 'SND_AUDIO_MYSTERY03',
                                  'SND_AUDIO_MYSTERY04', 'SND_AUDIO_MYSTERY05', 'SND_AUDIO_MYSTERY06'];
            var audio_missions = ['MIS_AUDIO_MYSTERY01', 'MIS_AUDIO_MYSTERY02', 'MIS_AUDIO_MYSTERY03',
                                  'MIS_AUDIO_MYSTERY04', 'MIS_AUDIO_MYSTERY05', 'MIS_AUDIO_MYSTERY06'];
            var rune_icons     = ['rune01.png', 'rune02.png', 'rune03.png', 'rune04.png', 'rune05.png', 'rune06.png'];
            var targets = ce4.gamestate.user.processed_picture_targets_list();
            var found_sounds  = 0;
            var found_sources = 0;
            var rows = '';
            for (var t=targets.length-1; t>=0; t--) {
                targets[t].sounds.forEach(function(sound) {
                    for (var s=0; s<target_sounds.length; s++) {
                        if (target_sounds[s] === sound.sound_key) {
                            found_sounds += 1;
                            var rune = 'rune_unknown.png';
                            // Has the corresponding obelisk been tagged?
                            var mission = ce4.gamestate.user.missions.for_definition(audio_missions[s]);
                            if (mission && mission.is_done()) {
                                found_sources += 1;
                                rune = rune_icons[s];
                            }
                            rows += '<tr><td><img src="/static/img/task_icons/'+rune+'"></td><td><div class="sound-control">\
                                      <iframe src="https://player.vimeo.com/video/'+sound.video_id+'" width="340" height="60"\
                                      frameborder="0" webkitAllowFullScreen mozallowfullscreen allowFullScreen></iframe>\
                                   </div></td></tr>';
                        }
                    }
                });
            }
            return '<table border=0 class="mission_sound_table"><td>Runes<br>('+found_sources+'&nbsp;of&nbsp;6)\
                    </td><td>Recorded clips<br>('+found_sounds+' of 6)' + rows + '</table>';
        }
    },

    // For the following missions & submissions, status callbacks return a count of the number of tags so far.
    MIS_SPECIES_FIND_5: {
        status: function() {
            return 'Tagged '+Math.min(5, ce4.gamestate.user.species.count_organic())+' of 5';
        }
    },
    MIS_SPECIES_FIND_10: {
        status: function() {
            return 'Tagged '+Math.min(10, ce4.gamestate.user.species.count_organic())+' of 10';
        }
    },
    MIS_SPECIES_FIND_15: {
        status: function() {
            return 'Tagged '+Math.min(15, ce4.gamestate.user.species.count_organic())+' of 15';
        }
    },
    MIS_SCI_FIND_COMMONa: {
        status: function() {
            var count = Math.min(2, ce4.gamestate.user.species.count_of_targets_for_key('SPC_PLANT021', 4));
            return 'Tagged '+count+' of 2';
        }
    },
    MIS_SCI_FIND_COMMONb: {
        status: function() {
            var count = Math.min(2, ce4.gamestate.user.species.count_of_targets_for_key('SPC_PLANT024', 4));
            return 'Tagged '+count+' of 2';
        }
    },
    MIS_SCI_FIND_COMMONc: {
        status: function() {
            var count = Math.min(2, ce4.gamestate.user.species.count_of_targets_for_key('SPC_PLANT019', 4));
            return 'Tagged '+count+' of 2';
        }
    },
    MIS_SCI_FLIGHT: {
        status: function() {
            var count = Math.min(3, ce4.gamestate.user.species.count_of_targets_for_key('SPC_ANIMAL004'));
            return 'Tagged '+count+' of 3';
        }
    },
    MIS_SCI_BIOLUMINESCENCE: {
        status: function() {
            // Groundbloom
            var str = '<br><br><span class="ce4_crosslink ce4_crosslink_catalog" data-species-key="SPC_PLANT015">Magenta</span>: Tagged '
                + Math.min(2, ce4.gamestate.user.species.count_of_targets_for_key('SPC_PLANT015', 5)) + ' of 2<br><br>';
            // Bluebloom
            str += '<span class="ce4_crosslink ce4_crosslink_catalog" data-species-key="SPC_PLANT031">Aqua</span>: Tagged '
                + Math.min(2, ce4.gamestate.user.species.count_of_targets_for_key('SPC_PLANT031', 5)) + ' of 2<br><br>';
            // Candlewort
            str += '<span class="ce4_crosslink ce4_crosslink_catalog" data-species-key="SPC_PLANT022">Red-orange</span>: Tagged '
                + Math.min(2, ce4.gamestate.user.species.count_of_targets_for_key('SPC_PLANT022', 5)) + ' of 2';
            return str;
        }
    },
    MIS_SCI_FLOWERS: {
        status: function() {
            var str = '<br><br>Closed</span>: Tagged '
                + Math.min(2, ce4.gamestate.user.species.count_of_targets_for_key('SPC_PLANT028', 0)) + ' of 2<br><br>';
            str += 'Open</span>: Tagged '
                + Math.min(2, ce4.gamestate.user.species.count_of_targets_for_key('SPC_PLANT028', 3)) + ' of 2<br><br>';
            return str;
        }
    },
    MIS_SCI_LIFECYCLE: {
        status: function() {
            var str = '<br><br>Juvenile</span>: '
                + (ce4.gamestate.user.species.count_of_targets_for_key('SPC_PLANT032', 1) ? 'Tagged' : 'Not tagged');
            str += '<br><br>Adult</span>: '
                + (ce4.gamestate.user.species.count_of_targets_for_key('SPC_PLANT032', 0) ? 'Tagged' : 'Not tagged');
            str += '<br><br>Deceased</span>: '
                + (ce4.gamestate.user.species.count_of_targets_for_key('SPC_PLANT032', 2) ? 'Tagged' : 'Not tagged');
            return str;
        }
    },
    MIS_SCI_CELLULARa: {
        status: function() {
            return 'Tagged '+Math.min(3, ce4.gamestate.user.species.count_of_targets_for_key('SPC_PLANT032'))+' of 3';
        }
    }
};
