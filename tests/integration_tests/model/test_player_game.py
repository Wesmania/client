import copy

from model.game import Game, GameState, GameVisibility
from model.gameset import Gameset
from model.playerset import Playerset
from model.player import Player

GAME_DICT = {
    "uid":  1,
    "state": GameState.OPEN,
    "launched_at": 10000,
    "num_players": 3,
    "max_players": 8,
    "title": "Sentons sucks",
    "host":  "Guy",
    "mapname": "Sentons Ultimate 6v6",
    "map_file_path": "xrca_co_000001.scfamap",
    "teams": {
        1: ["Guy", "TableNoob"],
        2: ["Kraut"]
        },
    "featured_mod": "faf",
    "featured_mod_versions": {},
    "sim_mods": {},
    "password_protected": False,
    "visibility": GameVisibility.PUBLIC,
}


def check_relation(game, player, exists):
    assert (player.currentGame is game) == exists
    assert (player in game.ingame_players) == exists


def setup():
    ps = Playerset()
    gs = Gameset(ps)

    p = Player(**{"id_": 1, "login": "Guy"})
    ps[p.id] = p
    p = Player(**{"id_": 2, "login": "TableNoob"})
    ps[p.id] = p
    p = Player(**{"id_": 3, "login": "Kraut"})
    ps[p.id] = p

    g = Game(playerset=ps, **GAME_DICT)
    gs[g.uid] = g
    return ps, gs


def test_setup():
    ps, gs = setup()
    for i in range(1, 3):
        assert ps[i].currentGame is gs[1]

    gps = gs[1].connected_players
    assert len(gps) == 3
    for i in range(1, 3):
        assert ps[1] in gps

    gps = gs[1].ingame_players
    assert len(gps) == 3
    for i in range(1, 3):
        assert ps[1] in gps


def test_player_at_game_change(mocker):
    ps = Playerset()
    gs = Gameset(ps)

    p = Player(**{"id_": 1, "login": "Guy"})
    ps[p.id] = p
    p = Player(**{"id_": 2, "login": "TableNoob"})
    ps[p.id] = p
    p = Player(**{"id_": 3, "login": "Kraut"})
    ps[p.id] = p

    data = copy.deepcopy(GAME_DICT)
    g1 = Game(playerset=ps, **data)

    gUpd = mocker.Mock()
    ps[1].newCurrentGame.connect(gUpd)

    gs[1] = g1
    gUpd.assert_called_with(ps[1], g1, None)
    gUpd.reset_mock()

    data["state"] = GameState.PLAYING
    gs[1].update(**data)

    assert not gUpd.called

    data["state"] = GameState.CLOSED
    gs[1].update(**data)
    gUpd.assert_called_with(ps[1], None, g1)


def test_player_at_another_game(mocker):
    ps, gs = setup()

    data = copy.deepcopy(GAME_DICT)
    data["uid"] = 2
    data["teams"] = {1: ["Guy"]}
    g2 = Game(playerset=ps, **data)

    gUpd = mocker.Mock()
    ps[1].newCurrentGame.connect(gUpd)

    gs[2] = g2
    gUpd.assert_called_with(ps[1], g2, gs[1])
    gUpd.reset_mock()

    # Test if closing the first game changes player state
    data = copy.deepcopy(GAME_DICT)
    data["state"] = GameState.CLOSED
    gs[1].update(**data)
    assert not gUpd.called


def test_game_at_missing_player(mocker):
    ps = Playerset()
    gs = Gameset(ps)

    p = Player(**{"id_": 1, "login": "Guy"})
    ps[p.id] = p
    p = Player(**{"id_": 2, "login": "TableNoob"})
    ps[p.id] = p

    data = copy.deepcopy(GAME_DICT)
    g1 = Game(playerset=ps, **data)
    pAdd = mocker.Mock()
    g1.connectedPlayerAdded.connect(pAdd)

    gs[1] = g1
    assert len(g1.players) == 3
    assert len(g1.connected_players) == 2
    assert ps[1] in g1.connected_players
    assert ps[2] in g1.connected_players

    assert not pAdd.called
    p = Player(**{"id_": 3, "login": "Kraut"})
    ps[p.id] = p
    pAdd.assert_called_with(g1, ps[3])

    assert len(g1.connected_players) == 3
    assert ps[3] in g1.connected_players
    assert ps[3] in g1.ingame_players
    assert ps[3].currentGame is g1


def test_remove_add_player(mocker):
    ps, gs = setup()

    pAdd = mocker.Mock()
    gs[1].connectedPlayerAdded.connect(pAdd)
    pRem = mocker.Mock()
    gs[1].connectedPlayerRemoved.connect(pRem)

    p3 = ps[3]
    del ps[3]
    pRem.assert_called_with(gs[1], p3)
    assert not pAdd.called
    assert p3 not in gs[1].connected_players

    pRem.reset_mock()

    ps[3] = p3
    pAdd.assert_called_with(gs[1], p3)
    assert not pRem.called
    assert p3 in gs[1].connected_players


def test_game_at_another_game(mocker):
    ps, gs = setup()

    data = copy.deepcopy(GAME_DICT)
    data["uid"] = 2
    data["teams"] = {1: ["Guy"]}
    g2 = Game(playerset=ps, **data)

    pRem = mocker.Mock()
    gs[1].ingamePlayerRemoved.connect(pRem)

    gs[2] = g2
    pRem.assert_called_with(gs[1], ps[1])

    check_relation(gs[1], ps[1], False)


def test_game_abort_removes_relation(mocker):
    ps, gs = setup()
    gUpd = mocker.Mock()
    ps[1].newCurrentGame.connect(gUpd)

    g1 = gs[1]
    gs[1].abort_game()
    gUpd.assert_called_with(ps[1], None, g1)
    for i in range(1, 3):
        assert ps[i].currentGame is None
    assert g1.ingame_players == []


def test_game_closed_removes_relation(mocker):
    ps, gs = setup()
    gUpd = mocker.Mock()
    ps[1].newCurrentGame.connect(gUpd)

    data = copy.deepcopy(GAME_DICT)
    data["state"] = GameState.CLOSED

    g1 = gs[1]
    gs[1].update(**data)

    gUpd.assert_called_with(ps[1], None, g1)
    for i in range(1, 3):
        assert ps[i].currentGame is None
    assert g1.ingame_players == []


def test_game_closed_removes_only_own(mocker):
    ps, gs = setup()

    data = copy.deepcopy(GAME_DICT)
    data["uid"] = 2
    data["teams"] = {1: ["Guy"]}
    g2 = Game(playerset=ps, **data)
    gs[2] = g2

    data = copy.deepcopy(GAME_DICT)
    data["state"] = GameState.CLOSED
    gs[1].update(**data)

    assert ps[1].currentGame is gs[2]
    assert ps[2].currentGame is None
    assert ps[3].currentGame is None
