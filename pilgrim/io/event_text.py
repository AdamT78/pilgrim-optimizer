"""One reader-facing line per game event, shared by the CLI and the play view.

`format_event` returns `None` for an event that has nothing to say to a reader. That is not the
same as an empty string: a caller must skip it rather than print it, or the transcript grows blank
lines where the engine happened to record bookkeeping.

This lives away from the CLI because two things now render event text. If it stayed there the
second one would either import a private name out of a command-line entrypoint or -- far worse --
grow a second wording of the same event, and the two would drift apart one event at a time.
"""

from __future__ import annotations

from pilgrim.model.actions import readable_route
from pilgrim.model.config import GameConfig
from pilgrim.model.duties import duty_category_at_position
from pilgrim.model.enums import EventType, position_name
from pilgrim.model.events import GameEvent


def _parse_route(route_text: str) -> tuple[int, ...]:
    if not route_text:
        return ()
    return tuple(int(piece) for piece in route_text.split("->"))


def format_event(event: GameEvent, config: GameConfig) -> str | None:
    details = dict(event.details)
    positions = config.board.positions
    event_name = event.event_type.value.upper()
    actor_name = event.actor.name.lower()

    if event.event_type is EventType.SOWING:
        source = int(details.get("source", -1))
        picked_up = details.get("picked_up", "?")
        route_text = str(details.get("route", ""))
        route = _parse_route(route_text)
        text = (
            f"{event_name}: picked up {picked_up} from {position_name(source, positions)}; "
            f"route {readable_route(source, route, positions=positions)}"
        )
        skipped = details.get("skipped")
        if skipped is not None and str(details.get("route_modifier", "")) == "cloisters":
            text += f"; skipped {position_name(int(skipped), positions)} with Cloisters"
        return text

    if event.event_type is EventType.SETUP_SOWING:
        source = int(details.get("source", -1))
        picked_up = details.get("picked_up", "?")
        route_names = str(details.get("route_names", "")).strip()
        if not route_names:
            route_text = str(details.get("route", ""))
            route = _parse_route(route_text)
            route_names = readable_route(source, route, positions=positions)
        return (
            f"{event_name}: {actor_name} picked up {picked_up} from "
            f"{position_name(source, positions)}; route {route_names}"
        )

    if event.event_type is EventType.SETUP_SOW_COMPLETE:
        player_name = str(details.get("player", actor_name))
        return f"{event_name}: {player_name} completed setup sow"

    if event.event_type is EventType.SETUP_PLAYER_ADVANCE:
        from_player = str(details.get("from_player", actor_name))
        to_player = str(details.get("to_player", "unknown"))
        return f"{event_name}: {from_player} -> {to_player}"

    if event.event_type is EventType.SETUP_COMPLETE:
        start_player = str(details.get("start_player", "unknown"))
        return (
            f"{event_name}: all players completed setup sow; normal play begins with {start_player}"
        )

    if event.event_type is EventType.DUTY_RESOLUTION:
        duty_position = details.get("duty_position")
        duty_label = (
            position_name(int(duty_position), positions)
            if isinstance(duty_position, int)
            else "unknown"
        )
        duty_category = str(details.get("duty_category", "")).strip()
        duty_with_category = f"{duty_label} ({duty_category})" if duty_category else duty_label
        if details.get("mode") == "tithe":
            line = f"{event_name}: selected {duty_with_category}; mode tithe"
            tithe_resource = details.get("tithe_resource")
            if tithe_resource:
                line += f"; gained {tithe_resource}"
            return line
        fragments = [f"selected {duty_with_category}"]
        if "strength" in details:
            fragments.append(f"relation {details['strength']}")
        if "duty_value" in details:
            fragments.append(f"duty value {details['duty_value']}")
        if "effective_duty_value" in details:
            effective_duty_value = int(details["effective_duty_value"])
            base_duty_value = int(details.get("duty_value", effective_duty_value))
            if effective_duty_value != base_duty_value:
                fragments.append(f"effective duty value {effective_duty_value}")
        if "silver_cost" in details:
            fragments.append(f"silver cost {details['silver_cost']}")
        if "effect" in details:
            fragments.append(f"action {details['effect']}")
        return f"{event_name}: {'; '.join(fragments)}"

    if event.event_type is EventType.DUTY_DEFERRED:
        scaffold = str(details.get("scaffold", "")).strip()
        effective_duty_value = details.get("effective_duty_value")
        spent = details.get("spent")
        if scaffold:
            if isinstance(effective_duty_value, int) and spent is False:
                return (
                    f"{event_name}: {scaffold}; effective duty value "
                    f"{effective_duty_value} not spent in this scaffold"
                )
            return f"{event_name}: {scaffold}"
        return f"{event_name}: {details}"

    if event.event_type is EventType.RESOURCE_DELTA:
        stone = int(details.get("stone", 0))
        silver = int(details.get("silver", 0))
        wheat = int(details.get("wheat", 0))
        piety = int(details.get("piety", 0))
        fragments: list[str] = []
        if stone != 0:
            fragments.append(f"stone {stone:+d}")
        if silver != 0:
            fragments.append(f"silver {silver:+d}")
        if wheat != 0:
            fragments.append(f"wheat {wheat:+d}")
        if piety != 0:
            fragments.append(f"piety {piety:+d}")
        if not fragments:
            return None
        return f"{event_name}: {actor_name} {'; '.join(fragments)}"

    if event.event_type is EventType.PIETY_DELTA:
        if "old_piety_position" in details and "new_piety_position" in details:
            old_position = int(details["old_piety_position"])
            new_position = int(details["new_piety_position"])
            if old_position == new_position:
                return None
            old_vp = int(details.get("old_piety_vp", 0))
            new_vp = int(details.get("new_piety_vp", 0))
            return (
                f"{event_name}: {actor_name} piety {old_position} -> {new_position}; "
                f"track VP {old_vp} -> {new_vp}"
            )
        amount = int(details.get("piety", 0))
        if amount == 0:
            return None
        return f"{event_name}: {actor_name} {amount:+d} piety"

    if event.event_type is EventType.ACOLYTE_RECALL:
        duty_position = int(details.get("duty_position", -1))
        recalled = int(details.get("recalled", 0))
        duty_label = position_name(duty_position, positions)
        return f"{event_name}: recalled {recalled} from {duty_label} to city"

    if event.event_type is EventType.INVARIANT_CHECK:
        if details.get("acolytes_conserved") is True:
            workforce_entries = [
                (str(key), value)
                for key, value in details.items()
                if str(key).startswith("total_workforce_player_") and isinstance(value, int)
            ]
            if workforce_entries:
                player_order = {
                    "total_workforce_player_one": 0,
                    "total_workforce_player_two": 1,
                    "total_workforce_player_three": 2,
                    "total_workforce_player_four": 3,
                }
                workforce_entries.sort(key=lambda item: player_order.get(item[0], 999))
                workforce_text = ", ".join(
                    f"{key.replace('total_workforce_', '', 1)}={value}"
                    for key, value in workforce_entries
                )
                conserved_label = (
                    "serfs/acolytes conserved"
                    if details.get("serfs_non_negative") is True
                    else "acolytes conserved"
                )
                return (
                    f"{event_name}: passed for all players "
                    f"({conserved_label}; total workforce by player: "
                    f"{workforce_text})"
                )
            total_workforce = details.get("total_workforce")
            if isinstance(total_workforce, int):
                return (
                    f"{event_name}: passed (acolytes conserved; total workforce={total_workforce})"
                )
            return f"{event_name}: passed (acolytes conserved)"
        return f"{event_name}: {details}"

    if event.event_type is EventType.ALMS_PAYMENT:
        credited_silver = details.get("credited_silver")
        credited_wheat = details.get("credited_wheat")
        actual_paid_silver = details.get("actual_paid_silver")
        actual_paid_wheat = details.get("actual_paid_wheat")

        if (
            credited_silver is not None
            and credited_wheat is not None
            and actual_paid_silver is not None
            and actual_paid_wheat is not None
        ):
            text = (
                f"{event_name}: {actor_name} credited silver={int(credited_silver)}, "
                f"wheat={int(credited_wheat)} toward Give Alms; actual paid "
                f"silver={int(actual_paid_silver)}, wheat={int(actual_paid_wheat)}"
            )
        else:
            silver = int(details.get("silver", 0))
            wheat = int(details.get("wheat", 0))
            text = f"{event_name}: {actor_name} paid silver={silver}, wheat={wheat}"
        minority_silver_cost = int(details.get("minority_silver_cost", 0))
        if minority_silver_cost > 0:
            text += f" (plus minority silver cost {minority_silver_cost})"
        return text

    if event.event_type is EventType.BUILDING_DONATION:
        building_name = str(details.get("building_name", "")).strip()
        building_id = str(details.get("building_id", "")).strip()
        donated_label = building_name if building_name else building_id
        donation_vp = int(details.get("donation_vp", 0))
        return f"{event_name}: {actor_name} donated {donated_label}; donation_vp={donation_vp}"

    if event.event_type is EventType.BUILDING_CONSTRUCTED:
        building_name = str(details.get("building_name", "")).strip()
        building_id = str(details.get("building_id", "")).strip()
        built_label = building_name if building_name else building_id
        source = str(details.get("source", "market"))
        level = int(details.get("level", 0))
        stone_cost = int(details.get("stone_cost", 0))
        active_count = int(details.get("active_buildings_count", 0))
        used_slots = int(details.get("used_slots", 0))
        slot_limit = int(details.get("slot_limit", 0))
        text = (
            f"{event_name}: {actor_name} constructed {built_label} from {source}; "
            f"level {level}; cost stone {stone_cost}; active buildings now {active_count}"
        )
        if slot_limit > 0:
            text += f"; used slots {used_slots}/{slot_limit}"
        else:
            text += f"; used slots {used_slots}"
        return text

    if event.event_type is EventType.BUILDING_HIRED:
        building_name = str(details.get("building_name", "")).strip()
        building_id = str(details.get("building_id", "")).strip()
        hired_label = building_name if building_name else building_id
        source = str(details.get("source", "unknown"))
        if details.get("free_with_wagon_yard") is True:
            return (
                f"{event_name}: {actor_name} hired {hired_label} from {source} "
                "for free with Wagon Yard"
            )
        payee = str(details.get("payee", "unknown"))
        resource = str(details.get("resource", "none"))
        amount = int(details.get("amount", 0))
        if amount > 0 and resource != "none":
            return (
                f"{event_name}: {actor_name} hired {hired_label} from {source}; "
                f"paid {resource} {amount} to {payee}"
            )
        return f"{event_name}: {actor_name} used {hired_label} from {source}; no payment"

    if event.event_type is EventType.WORKFORCE_MOVE:
        amount = int(details.get("amount", 1))
        unit = str(details.get("unit", "worker"))
        from_pool = str(details.get("from_pool", "unknown"))
        to_pool = str(details.get("to_pool", "unknown"))
        wheat_paid = int(details.get("wheat_paid", 0))
        building = str(details.get("building", "")).strip().lower()
        if wheat_paid == 0 and building == "pulpit":
            return (
                f"{event_name}: {actor_name} moved {amount} {unit} "
                f"{from_pool} -> {to_pool} for free with Pulpit"
            )
        paid_suffix = "for free" if wheat_paid == 0 else f"paid wheat={wheat_paid}"
        return (
            f"{event_name}: {actor_name} moved {amount} {unit} "
            f"{from_pool} -> {to_pool}; {paid_suffix}"
        )

    if event.event_type is EventType.ORDINATION:
        step = str(details.get("step", "")).strip()
        amount = int(details.get("amount", 1))
        from_pool = str(details.get("from_pool", "unknown"))
        to_pool = str(details.get("to_pool", "unknown"))
        wheat_paid = int(details.get("wheat_paid", 1))
        bank_silver_paid = int(details.get("bank_silver_paid", 0))
        bank_paid_suffix = (
            f"; paid {bank_silver_paid} silver via Bank" if bank_silver_paid > 0 else ""
        )
        if step == "ordain":
            return (
                f"{event_name}: {actor_name} ordained {amount} serf {from_pool} -> {to_pool}; "
                f"paid wheat={wheat_paid}{bank_paid_suffix}"
            )
        if step == "mission":
            return (
                f"{event_name}: {actor_name} sent {amount} acolyte {from_pool} -> {to_pool}; "
                f"paid wheat={wheat_paid}{bank_paid_suffix}"
            )
        return (
            f"{event_name}: {actor_name} step={step} moved {amount} {from_pool} -> {to_pool}; "
            f"paid wheat={wheat_paid}{bank_paid_suffix}"
        )

    if event.event_type is EventType.TAXATION:
        step = str(details.get("step", "")).strip()
        if step == "step_1":
            resource = str(details.get("resource", "unknown"))
            return f"{event_name}: {actor_name} took step 1 resource {resource}"
        if step == "step_2":
            no_bonus = bool(details.get("no_bonus", False))
            resources_csv = str(details.get("resources", "")).strip()
            if no_bonus or not resources_csv:
                return (
                    f"{event_name}: {actor_name} had no other majority duty tiles;"
                    " no bonus resources"
                )
            resources_text = ", ".join(
                resource for resource in resources_csv.split(",") if resource
            )
            return (
                f"{event_name}: {actor_name} took bonus resources {resources_text} "
                "from other majority duty tiles"
            )
        return f"{event_name}: {actor_name} {details}"

    if event.event_type is EventType.ALMS_PROGRESS:
        old_row = int(details.get("old_row", 0))
        new_row = int(details.get("new_row", 0))
        return f"{event_name}: {actor_name} row {old_row} -> {new_row}"

    if event.event_type is EventType.ALMS_THRESHOLD_REWARD:
        description = str(details.get("description", "")).strip()
        if description:
            return f"{event_name}: {description}"
        threshold = int(details.get("threshold", -1))
        reward = str(details.get("reward", "unknown"))
        moved = bool(details.get("moved", False))
        return f"{event_name}: crossed row {threshold}; reward={reward}; moved={moved}"

    if event.event_type is EventType.ALMS_SEASON_END:
        winner = str(details.get("winner", "unknown"))
        round_number = int(details.get("round", 0))
        site = details.get("season_site")
        tie_break = str(details.get("tie_break", ""))
        winner_alms = int(details.get("winning_alms_position", 0))
        winner_piety = int(details.get("winning_piety", 0))
        site_text = f" site {int(site)}" if site is not None else ""
        tie_break_text = {
            "highest_alms_position": "highest Alms position",
            "higher_piety": "higher piety",
            "turn_order": "current turn order",
        }.get(tie_break, tie_break or "tie-break")
        return (
            f"{event_name}: round {round_number} reached pilgrimage{site_text}; "
            f"leader {winner} by {tie_break_text} "
            f"(alms={winner_alms}, piety={winner_piety})"
        )

    if event.event_type is EventType.ALMS_SEASON_REWARD:
        winner = str(details.get("winner", "unknown"))
        moved = bool(details.get("moved", False))
        if moved:
            acolytes = int(details.get("alms_table_acolytes", 0))
            end_game_vp = int(details.get("end_game_vp", 0))
            return (
                f"{event_name}: {winner} moved 1 acolyte abbey -> alms_table; "
                f"alms table acolytes {acolytes}; end-game VP {end_game_vp}"
            )
        if bool(details.get("forfeited", False)):
            return (
                f"{event_name}: {winner} won Alms season end but had no Abbey acolyte; "
                "reward forfeited"
            )
        return f"{event_name}: {winner} had no abbey acolyte to move"

    if event.event_type is EventType.ALMS_RESET:
        return f"{event_name}: all players reset to row 0"

    if event.event_type is EventType.ALLOCATION:
        from_pool = str(details.get("from_pool", "unknown"))
        to_pool = str(details.get("to_pool", "unknown"))
        amount = int(details.get("amount", 0))
        return f"{event_name}: {actor_name} moved {amount} acolyte {from_pool} -> {to_pool}"

    if event.event_type is EventType.START_TURN_RELOCATION:
        from_position = int(details.get("from_position", -1))
        to_position = int(details.get("to_position", -1))
        amount = int(details.get("amount", 1))
        building_name = str(details.get("building_name", details.get("building", "unknown")))
        return (
            f"{event_name}: {actor_name} moved {amount} acolyte "
            f"{position_name(from_position, positions)} -> {position_name(to_position, positions)} "
            f"using {building_name}"
        )

    if event.event_type is EventType.END_TURN_RELOCATION:
        from_pool = str(details.get("from_pool", "city"))
        to_pool = str(details.get("to_pool", "unknown"))
        amount = int(details.get("amount", 1))
        building_name = str(details.get("building_name", details.get("building", "unknown")))
        return (
            f"{event_name}: {actor_name} moved {amount} acolyte "
            f"{from_pool} -> {to_pool} using {building_name}"
        )

    if event.event_type is EventType.BUILDING_BONUS:
        building = str(details.get("building", "unknown"))
        action_name = str(details.get("action", "unknown"))
        if (
            building == "chapter_house"
            and action_name == "allocation"
            and details.get("second_acolyte") is True
        ):
            activity = str(details.get("activity", "unknown"))
            capacity = int(details.get("capacity", 2))
            return (
                f"{event_name}: chapter_house allowed second acolyte on "
                f"{activity} (capacity {capacity})"
            )
        if building == "mill" and "wheat_waived" in details:
            wheat_waived = int(details.get("wheat_waived", 0))
            return f"{event_name}: mill waived wheat cost {wheat_waived} for {action_name}"
        if building == "kogge" and "enabled_route" in details:
            enabled_route = str(details.get("enabled_route", "")).strip()
            return f"{event_name}: kogge enabled {enabled_route} sow route"
        if building == "cloisters" and "skipped_location" in details:
            skipped_location = str(details.get("skipped_location", "unknown"))
            return f"{event_name}: cloisters skipped {skipped_location} during sow route"
        if building == "grain_store" and "conversion_direction" in details and "amount" in details:
            amount = int(details.get("amount", 0))
            direction = str(details.get("conversion_direction", "unknown"))
            if direction == "sell_wheat":
                return f"{event_name}: grain_store sold {amount} wheat for {amount} silver"
            if direction == "buy_wheat":
                return f"{event_name}: grain_store bought {amount} wheat for {amount} silver"
        if building == "indulgences" and "conversion_direction" in details and "amount" in details:
            amount = int(details.get("amount", 0))
            direction = str(details.get("conversion_direction", "unknown"))
            if direction == "sell_piety":
                return f"{event_name}: indulgences sold {amount} piety for {amount} silver"
            if direction == "buy_piety":
                return f"{event_name}: indulgences bought {amount} piety for {amount} silver"
        if building == "stone_yard" and "conversion_direction" in details and "amount" in details:
            amount = int(details.get("amount", 0))
            direction = str(details.get("conversion_direction", "unknown"))
            if direction == "sell_stone":
                return f"{event_name}: stone_yard sold {amount} stone for {amount} silver"
            if direction == "buy_stone":
                return f"{event_name}: stone_yard bought {amount} stone for {amount} silver"
        if building == "brewery" and "conversion_direction" in details and "amount" in details:
            direction = str(details.get("conversion_direction", "unknown"))
            if direction == "sell_wheat_for_silver":
                return f"{event_name}: brewery sold 1 wheat for 2 silver"
        if (
            building == "bank"
            and action_name == "payment_substitution"
            and "replaced_resource" in details
            and "silver_amount" in details
        ):
            replaced_resource = str(details.get("replaced_resource", "unknown"))
            silver_amount = int(details.get("silver_amount", 0))
            return (
                f"{event_name}: bank replaced {silver_amount} {replaced_resource} "
                f"with {silver_amount} silver for this transaction"
            )
        if building == "scriptorium" and action_name == "effective_acolyte_bonus":
            return (
                f"{event_name}: scriptorium added +1 effective acolyte "
                "on occupied Duty tiles this turn"
            )
        if building == "customs_house" and action_name == "taxation_majority_override":
            return (
                f"{event_name}: customs_house claimed Taxation majority "
                "on occupied Duty tiles this turn"
            )
        if building == "guild" and action_name == "merchant_advance":
            return f"{event_name}: guild moved Merchant clockwise +1"
        if building == "pulpit" and action_name == "workforce_move":
            return f"{event_name}: pulpit moved 1 serf village -> abbey for free"
        if (
            building in ("dormitory", "inquisition")
            and "start_turn_from" in details
            and "start_turn_to" in details
        ):
            start_turn_from = str(details.get("start_turn_from", "unknown"))
            start_turn_to = str(details.get("start_turn_to", "unknown"))
            if building == "dormitory":
                return (
                    f"{event_name}: dormitory returned 1 acolyte from "
                    f"{start_turn_from} to {start_turn_to}"
                )
            return (
                f"{event_name}: inquisition moved 1 acolyte from "
                f"{start_turn_from} to {start_turn_to}"
            )
        if building == "library" and "end_turn_from" in details and "end_turn_to" in details:
            end_turn_from = str(details.get("end_turn_from", "unknown"))
            end_turn_to = str(details.get("end_turn_to", "unknown"))
            return f"{event_name}: library moved 1 acolyte from {end_turn_from} to {end_turn_to}"
        bonuses: list[str] = []
        if "wheat_bonus" in details:
            bonuses.append(f"wheat +{int(details['wheat_bonus'])}")
        if "stone_bonus" in details:
            bonuses.append(f"stone +{int(details['stone_bonus'])}")
        if "silver_bonus" in details:
            bonuses.append(f"silver +{int(details['silver_bonus'])}")
        if "piety_bonus" in details:
            bonuses.append(f"piety +{int(details['piety_bonus'])}")
        if "duty_value_bonus" in details:
            bonuses.append(f"duty value +{int(details['duty_value_bonus'])}")
        if bonuses:
            text = f"{event_name}: {building} added {', '.join(bonuses)} to {action_name}"
            if details.get("extra_wheat_cost_paid") is True:
                text += "; extra wheat cost paid"
            return text
        return f"{event_name}: {building} applied to {action_name}"

    if event.event_type is EventType.SPECIAL_ACTIVITY_BONUS:
        activity = str(details.get("activity", "unknown"))
        action_name = str(details.get("action", "unknown"))
        if activity == "alms_house" and "duty_value_bonus" in details:
            text = f"{event_name}: {activity} applied to {action_name}"
            text += f"; duty value +{int(details['duty_value_bonus'])}"
            return text
        if activity == "road_engineer" and (
            details.get("construct_extra_road") is True or "construct_extra_roads" in details
        ):
            extra_roads = int(details.get("construct_extra_roads", 1))
            if extra_roads <= 1:
                return (
                    f"{event_name}: road_engineer allowed one additional road for construct "
                    "because a road was included in the plan"
                )
            return (
                f"{event_name}: road_engineer allowed {extra_roads} additional roads for construct "
                "because a road was included in the plan"
            )
        bonuses: list[str] = []
        if "wheat_bonus" in details:
            bonuses.append(f"wheat +{int(details['wheat_bonus'])}")
        if "stone_bonus" in details:
            bonuses.append(f"stone +{int(details['stone_bonus'])}")
        if "silver_bonus" in details:
            bonuses.append(f"silver +{int(details['silver_bonus'])}")
        if "piety_bonus" in details:
            bonuses.append(f"piety +{int(details['piety_bonus'])}")
        if "duty_value_bonus" in details:
            bonuses.append(f"duty value +{int(details['duty_value_bonus'])}")
        if bonuses:
            text = f"{event_name}: {activity} added {', '.join(bonuses)} to {action_name}"
        else:
            text = f"{event_name}: {activity} applied to {action_name}"
        return text

    if event.event_type is EventType.EXCESS_CHECK:
        if details.get("no_excess") is True:
            return f"{event_name}: no excess resources"
        return f"{event_name}: {details}"

    if event.event_type is EventType.EXCESS_RESOURCE_CAP:
        player = str(details.get("player", "unknown"))
        parts: list[str] = []
        if "stone_before" in details and "stone_after" in details:
            parts.append(f"stone {int(details['stone_before'])} -> {int(details['stone_after'])}")
        if "wheat_before" in details and "wheat_after" in details:
            parts.append(f"wheat {int(details['wheat_before'])} -> {int(details['wheat_after'])}")
        if not parts:
            return f"{event_name}: {player} had capped resources"
        return f"{event_name}: {player} " + "; ".join(parts)

    if event.event_type is EventType.EXCESS_DISCARD:
        player = str(details.get("player", "unknown"))
        resource = str(details.get("resource", "unknown"))
        before = int(details.get("before", 0))
        after = int(details.get("after", 0))
        returned = int(details.get("returned", max(before - after, 0)))
        return (
            f"{event_name}: {player} {resource} {before} -> {after}; returned {returned} to supply"
        )

    if event.event_type is EventType.SHIP_ADVANCE:
        from_position = int(details.get("from_position", -1))
        to_position = int(details.get("to_position", -1))
        pilgrimage = bool(details.get("at_pilgrimage_site", False))
        nw_site = bool(details.get("at_nw_pilgrimage_site", False))
        return (
            f"{event_name}: {from_position} -> {to_position}; "
            f"pilgrimage_site={str(pilgrimage).lower()}; "
            f"nw_site={str(nw_site).lower()}"
        )

    if event.event_type is EventType.DUMMY_ACOLYTE_MOVE:
        group = str(details.get("group", "unknown"))
        from_position = int(details.get("from_position", -1))
        to_position = int(details.get("to_position", -1))
        from_label = position_name(from_position, positions)
        to_label = position_name(to_position, positions)
        before_positions = str(details.get("before_positions", "")).strip()
        after_positions = str(details.get("after_positions", "")).strip()
        if before_positions and after_positions:
            return (
                f"{event_name}: {group} before [{before_positions}]; "
                f"moved {from_label} -> {to_label}; "
                f"after [{after_positions}]"
            )
        return f"{event_name}: {group} moved {from_label} -> {to_label}"

    if event.event_type is EventType.MERCHANT_ADVANCE:
        from_duty = str(details.get("from_duty", "unknown"))
        to_duty = str(details.get("to_duty", "unknown"))
        current_resource = str(details.get("current_resource", "none"))
        to_position = str(details.get("to_position", "unknown"))
        text = (
            f"{event_name}: {from_duty} -> {to_duty} ({to_position}); "
            f"current resource={current_resource}"
        )
        cause = details.get("cause")
        if cause is not None:
            text += f"; cause={str(cause)}"
        return text

    if event.event_type is EventType.TRADE_ROUTE_INCOME:
        player = str(details.get("player", actor_name))
        resource = str(details.get("resource", "unknown"))
        amount = int(details.get("amount", 0))
        trade_routes = int(details.get("trade_routes", 0))
        route_label = "trade route" if trade_routes == 1 else "trade routes"
        return (
            f"{event_name}: {player} gained {resource} +{amount} from {trade_routes} {route_label}"
        )

    if event.event_type is EventType.CONFESSION_BOX_BONUS:
        player = str(details.get("player", actor_name))
        source = str(details.get("source", "unknown"))
        base_piety = int(details.get("base_piety", 0))
        temporary_bonus = int(details.get("temporary_bonus", 0))
        effective_piety = int(details.get("effective_piety", base_piety + temporary_bonus))
        source_text = (
            "own active Confession Box"
            if source == "own_active"
            else (
                "Confession Box from market"
                if source == "market"
                else f"Confession Box from {source}"
            )
        )
        return (
            f"{event_name}: {player} used {source_text}; temporary piety "
            f"{base_piety} + {temporary_bonus} = {effective_piety} for start-player selection"
        )

    if event.event_type is EventType.CONFESSION_BOX_DECLINED:
        player = str(details.get("player", actor_name))
        return f"{event_name}: {player} declined the Confession Box"

    if event.event_type is EventType.CONFESSION_BOX_PHASE:
        first_player = str(details.get("first_player", "unknown"))
        turn_order = str(details.get("turn_order", ""))
        order_text = ", ".join(turn_order.split(",")) if turn_order else "none"
        return (
            f"{event_name}: Confession Boxes are decided before the marker, in turn order "
            f"{order_text}; waiting on {first_player}"
        )

    if event.event_type is EventType.TRADE_ROUTE_INCOME_SKIPPED:
        return f"{event_name}: trade routes not implemented"

    if event.event_type is EventType.START_PLAYER_TIE_BREAK:
        tied_players = str(details.get("tied_players", ""))
        current_start = str(details.get("current_start_player", "unknown"))
        deciding_player = str(details.get("deciding_player", "unknown"))
        tied_labels = ", ".join(tied_players.split(",")) if tied_players else "none"
        return (
            f"{event_name}: tied players [{tied_labels}]; "
            f"current start player {current_start}; deciding player {deciding_player}"
        )

    if event.event_type is EventType.START_PLAYER_MARKER:
        deciding_player = str(details.get("deciding_player", "unknown"))
        effective_piety = details.get("highest_effective_piety", "unknown")
        return (
            f"{event_name}: {deciding_player} takes the First Player marker on effective piety "
            f"{effective_piety} and must choose who begins this round"
        )

    if event.event_type is EventType.START_PLAYER_SELECTION:
        # Both names, every time, including when they are the same name twice. This is the one line
        # in the log where the decider and the player they chose are visibly two things, so it is
        # the one line that may not drop either. Shortening the self-selection to "chose to begin"
        # would leave a reader working out from a MISSING name whether the holder kept the round or
        # the message elided who they gave it to, and those read alike while meaning opposites.
        deciding_player = str(details.get("deciding_player", "unknown"))
        selected_player = str(details.get("selected_start_player", "unknown"))
        return f"{event_name}: {deciding_player} chose {selected_player} to begin this round"

    if event.event_type is EventType.GAME_END:
        reason = str(details.get("reason", "")).strip()
        if reason:
            return f"{event_name}: {reason}"
        return f"{event_name}: game over"

    if event.event_type is EventType.TURN_ADVANCE:
        from_player = str(details.get("from_player", "unknown"))
        to_player = str(details.get("to_player", "unknown"))
        return f"{event_name}: {from_player} -> {to_player}"

    if event.event_type is EventType.ROUND_END:
        round_number = int(details.get("round", 0))
        return f"{event_name}: round {round_number} complete"

    if event.event_type is EventType.ROUND_ADVANCE:
        from_round = int(details.get("from_round", 0))
        to_round = int(details.get("to_round", 0))
        return f"{event_name}: round {from_round} -> {to_round}"

    if event.event_type is EventType.SEASON_END:
        season_number = int(details.get("season", 0))
        return f"{event_name}: season {season_number} complete"

    if event.event_type is EventType.SEASON_END_DEFERRED:
        round_number = int(details.get("round", 0))
        return (
            f"{event_name}: round {round_number} reached pilgrimage site; "
            "Alms leader assessment deferred"
        )

    if event.event_type is EventType.SEASON_ADVANCE:
        from_season = int(details.get("from_season", 0))
        to_season = int(details.get("to_season", 0))
        return f"{event_name}: season {from_season} -> {to_season}"

    return f"{event_name}: {details}"


# KEEP THESE TWO TOGETHER.
# `format_event` is the developer/CLI voice and `format_event_for_players` is the in-page player
# voice. They are a pair by design: adding, removing or rewording one without checking the other is
# a drift bug waiting to happen.
def _title_words(value: str) -> str:
    return value.replace("_", " ").strip().title()


def _player_list(raw: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in raw.split(",") if part.strip())


def _join_players(players: tuple[str, ...]) -> str:
    if not players:
        return "unknown"
    if len(players) == 1:
        return players[0]
    if len(players) == 2:
        return f"{players[0]} and {players[1]}"
    return ", ".join(players[:-1]) + f", and {players[-1]}"


def _join_possessive_scores(players: tuple[str, ...], score: int) -> str:
    if not players:
        return f"others' {score}"
    if len(players) == 1:
        return f"{players[0]}'s {score}"
    possessive_names = [f"{player}'s" for player in players]
    if len(possessive_names) == 2:
        return f"{possessive_names[0]} and {possessive_names[1]} {score}"
    return ", ".join(possessive_names[:-1]) + f", and {possessive_names[-1]} {score}"


def _confession_bonus_suffix(details: dict) -> str:
    bonus_players = _player_list(str(details.get("confession_bonus_players", "")).strip())
    if not bonus_players:
        return ""
    return (
        " Confession Box bonus (+2) applied to "
        f"{_join_players(bonus_players)}."
    )


def _duty_label_for_players(details: dict, config: GameConfig) -> str:
    duty_category = str(details.get("duty_category", "")).strip()
    if duty_category:
        return _title_words(duty_category)
    duty_position = details.get("duty_position")
    if isinstance(duty_position, int):
        if duty_position == 0:
            return "City"
        try:
            return _title_words(duty_category_at_position(config, duty_position))
        except (TypeError, ValueError):
            return _title_words(position_name(duty_position, config.board.positions))
    return "Unknown Duty"


def _resolution_label_for_bonus(action_name: str) -> str:
    if action_name.startswith("produce_"):
        return "Produce"
    if action_name.startswith("construct"):
        return "Construct"
    if action_name.startswith("build_roads"):
        return "Build Roads"
    if action_name.startswith("give_alms"):
        return "Give Alms"
    if action_name.startswith("clerical_"):
        return "Clerical"
    return _title_words(action_name)


def _times_word(value: int) -> str:
    if value == 1:
        return "once"
    if value == 2:
        return "twice"
    return f"{value} times"


def _resource_bonus_player_line(
    *,
    actor: str,
    details: dict,
    source_name: str,
) -> str | None:
    if bool(details.get("player_line_suppressed", False)):
        return None

    action_name = str(details.get("action", "")).strip()
    at = _resolution_label_for_bonus(action_name) if action_name else "this action"
    for key, resource in (
        ("wheat_bonus", "wheat"),
        ("stone_bonus", "stone"),
        ("silver_bonus", "silver"),
        ("piety_bonus", "piety"),
    ):
        amount = int(details.get(key, 0))
        if amount == 0:
            continue
        total = int(details.get("total_amount", amount))
        base = int(details.get("base_amount", max(total - amount, 0)))
        source_ids = [
            source.strip()
            for source in str(details.get("player_bonus_sources", "")).split(",")
            if source.strip()
        ]
        source_amount_tokens = [
            token.strip()
            for token in str(details.get("player_bonus_amounts", "")).split(",")
            if token.strip()
        ]
        source_amounts: list[int] = []
        for token in source_amount_tokens:
            try:
                source_amounts.append(int(token))
            except ValueError:
                source_amounts = []
                break
        source_clauses: list[str] = []
        if source_ids and source_amounts and len(source_ids) == len(source_amounts):
            source_clauses = [
                f"{bonus} from the {_title_words(source_id)}"
                for source_id, bonus in zip(source_ids, source_amounts, strict=True)
                if bonus != 0
            ]
        else:
            source_clauses = [f"{amount} from the {source_name}"]
        clauses = ([f"{base} for the duty"] if base > 0 else []) + source_clauses
        if not clauses:
            return None
        return f"{actor} gained {total} {resource} at {at} \u2014 {', '.join(clauses)}."
    return None


def _bonus_delta_is_zero(details: dict) -> bool:
    keys = (
        "wheat_bonus",
        "stone_bonus",
        "silver_bonus",
        "piety_bonus",
        "duty_value_bonus",
        "wheat_waived",
    )
    seen = False
    for key in keys:
        if key not in details:
            continue
        seen = True
        if int(details.get(key, 0)) != 0:
            return False
    return seen


def _bonus_location_label(value: str) -> str:
    label = _title_words(value)
    return f"the {label}" if value == "city" else label


def _building_conversion_for_players(
    actor: str,
    *,
    building_name: str,
    details: dict,
) -> str | None:
    direction = str(details.get("conversion_direction", "")).strip()
    if not direction:
        return None

    conversions = {
        "buy_wheat": ("buy", "wheat", "silver", 1),
        "sell_wheat": ("sell", "wheat", "silver", 1),
        "buy_stone": ("buy", "stone", "silver", 1),
        "sell_stone": ("sell", "stone", "silver", 1),
        "buy_piety": ("buy", "piety", "silver", 1),
        "sell_piety": ("sell", "piety", "silver", 1),
        "sell_wheat_for_silver": ("sell", "wheat", "silver", 2),
    }
    conversion = conversions.get(direction)
    if conversion is None:
        return None
    verb, spent, received, rate = conversion
    amount = int(details.get("amount", 1))
    return (
        f"{actor} used the {building_name} to {verb} {amount} {spent} "
        f"for {amount * rate} {received}."
    )


def _building_bonus_for_players(actor: str, details: dict) -> str | None:
    if bool(details.get("player_line_suppressed", False)):
        return None

    building = str(details.get("building", "")).strip()
    if not building:
        return None
    source_name = _title_words(building)
    action_name = str(details.get("action", "")).strip()

    if "enabled_route" in details or "skipped_location" in details:
        return None

    if building == "mill" and "wheat_waived" in details:
        waived = int(details.get("wheat_waived", 0))
        due = int(details.get("required_wheat", 0))
        if due <= 0:
            due = waived
        spent = int(details.get("actual_wheat_spent", max(due - waived, 0)))
        if action_name == "ordination":
            if waived > 0:
                return (
                    f"{actor} paid {spent} wheat for Ordination "
                    f"\u2014 {due} due, {waived} waived by the {source_name}."
                )
            return f"{actor} paid {spent} wheat for Ordination."
        if waived == 0:
            return None
        at = _resolution_label_for_bonus(action_name) if action_name else "this action"
        return (
            f"{actor} paid {spent} wheat on {at} "
            f"\u2014 {due} due, {waived} waived by the {source_name}."
        )

    conversion_line = _building_conversion_for_players(
        actor,
        building_name=source_name,
        details=details,
    )
    if conversion_line is not None:
        return conversion_line

    if building == "bank" and action_name == "payment_substitution":
        replaced = str(details.get("replaced_resource", "resource")).strip()
        silver = int(details.get("silver_amount", 0))
        if silver > 0:
            return f"{actor} used the Bank to pay {silver} silver instead of {silver} {replaced}."

    if building == "chapter_house" and details.get("second_acolyte") is True:
        activity = _title_words(str(details.get("activity", "Special Activity")).strip())
        return f"{actor} used the Chapter House to place a second acolyte on the {activity}."

    if building == "scriptorium" and action_name == "effective_acolyte_bonus":
        return (
            f"{actor} used the Scriptorium to count one extra acolyte "
            "on each occupied Duty tile."
        )

    if building == "customs_house" and action_name == "taxation_majority_override":
        return f"{actor} used the Customs House to make occupied Duty tiles a Taxation majority."

    if building == "guild" and action_name == "merchant_advance":
        return f"{actor} used the Guild to move the Merchant one space clockwise."

    if building == "pulpit" and action_name == "workforce_move":
        return f"{actor} used the Pulpit to move a serf from the Village to the Abbey."

    if building in {"dormitory", "inquisition"} and "start_turn_from" in details:
        origin = _bonus_location_label(str(details.get("start_turn_from", "unknown")).strip())
        destination = _bonus_location_label(str(details.get("start_turn_to", "unknown")).strip())
        verb = "return" if building == "dormitory" else "move"
        return (
            f"{actor} used the {source_name} to {verb} an acolyte "
            f"from {origin} to {destination}."
        )

    if building == "library" and "end_turn_from" in details:
        origin = _bonus_location_label(str(details.get("end_turn_from", "unknown")).strip())
        destination = _bonus_location_label(str(details.get("end_turn_to", "unknown")).strip())
        return f"{actor} used the Library to move an acolyte from {origin} to {destination}."

    resource_line = _resource_bonus_player_line(
        actor=actor,
        details=details,
        source_name=source_name,
    )
    if resource_line is not None:
        return resource_line

    duty_bonus = int(details.get("duty_value_bonus", 0))
    if duty_bonus == 0 and "duty_value_bonus" in details:
        return None
    if duty_bonus:
        at = _resolution_label_for_bonus(action_name) if action_name else "this action"
        return f"{actor} gained {duty_bonus} duty value at {at} from the {source_name}."
    return None


def _special_activity_bonus_for_players(actor: str, details: dict) -> str | None:
    if bool(details.get("player_line_suppressed", False)):
        return None

    activity = str(details.get("activity", "")).strip()
    source_name = _title_words(activity) if activity else "Special Activity"
    action_name = str(details.get("action", "")).strip()

    if activity == "road_engineer" and "construct_extra_roads" in details:
        extra_roads = int(details.get("construct_extra_roads", 0))
        if extra_roads > 0:
            noun = "road" if extra_roads == 1 else "roads"
            return f"{actor} used the Road Engineer to build {extra_roads} additional {noun}."

    resource_line = _resource_bonus_player_line(
        actor=actor,
        details=details,
        source_name=source_name,
    )
    if resource_line is not None:
        return resource_line

    duty_bonus = int(details.get("duty_value_bonus", 0))
    if duty_bonus == 0 and "duty_value_bonus" in details:
        return None
    if duty_bonus:
        at = _resolution_label_for_bonus(action_name) if action_name else "this action"
        return f"{actor} gained {duty_bonus} duty value at {at} from the {source_name}."
    return None


_PLAYER_TURN_STEP_EVENT_TYPES: set[EventType] = {
    EventType.PIETY_DELTA,
    EventType.TAXATION,
    EventType.RESOURCE_DELTA,
    EventType.ALMS_PAYMENT,
    EventType.ALMS_PROGRESS,
    EventType.ALMS_THRESHOLD_REWARD,
    EventType.ACOLYTE_RECALL,
    EventType.ORDINATION,
    EventType.START_PLAYER_SELECTION,
}

_PLAYER_ROUND_END_EVENT_TYPES: set[EventType] = {
    EventType.SHIP_ADVANCE,
    EventType.MERCHANT_ADVANCE,
    EventType.START_PLAYER_TIE_BREAK,
    EventType.START_PLAYER_MARKER,
    EventType.ROUND_END,
}


_PLAYER_DROPPED_EVENT_TYPES: set[EventType] = {
    EventType.SOWING,
    EventType.SETUP_SOWING,
    EventType.SETUP_SOW_COMPLETE,
    EventType.SETUP_PLAYER_ADVANCE,
    EventType.DUTY_RESOLUTION,
    EventType.DUTY_DEFERRED,
    EventType.INVARIANT_CHECK,
    EventType.TRADE_ROUTE_INCOME_SKIPPED,
    EventType.TURN_ADVANCE,
    EventType.ROUND_ADVANCE,
    EventType.SEASON_ADVANCE,
    EventType.CONFESSION_BOX_PHASE,
}

_PLAYER_EXPLICIT_EVENT_TYPES: set[EventType] = {
    EventType.SETUP_COMPLETE,
    *_PLAYER_TURN_STEP_EVENT_TYPES,
    EventType.BUILDING_DONATION,
    EventType.BUILDING_CONSTRUCTED,
    EventType.BUILDING_HIRED,
    EventType.ALLOCATION,
    EventType.BUILDING_BONUS,
    EventType.SPECIAL_ACTIVITY_BONUS,
    *_PLAYER_ROUND_END_EVENT_TYPES,
}

PLAYER_EVENT_FALLBACK_TYPES: tuple[EventType, ...] = tuple(
    event_type
    for event_type in EventType
    if event_type not in (_PLAYER_DROPPED_EVENT_TYPES | _PLAYER_EXPLICIT_EVENT_TYPES)
)


def format_event_for_players(event: GameEvent, config: GameConfig) -> str | None:
    """One player-facing line per event, or None when this event is transcript-noise."""
    details = dict(event.details)
    actor = event.actor.name.lower()
    event_type = event.event_type

    if event_type in _PLAYER_DROPPED_EVENT_TYPES:
        return None

    if event_type is EventType.SETUP_COMPLETE:
        start_player = str(details.get("start_player", "unknown"))
        return f"Setup complete. {start_player} begins this round."

    if event_type is EventType.RESOURCE_DELTA:
        deltas = [
            ("stone", int(details.get("stone", 0))),
            ("silver", int(details.get("silver", 0))),
            ("wheat", int(details.get("wheat", 0))),
            ("piety", int(details.get("piety", 0))),
        ]
        changed = [(name, delta) for name, delta in deltas if delta != 0]
        if not changed:
            return None
        # One positive stock only is usually already named by the action summary line.
        if len(changed) == 1 and changed[0][1] > 0 and changed[0][0] != "piety":
            return None
        return f"{actor} " + "; ".join(f"{name} {delta:+d}" for name, delta in changed)

    if event_type is EventType.TAXATION:
        step = str(details.get("step", "")).strip()
        if step == "step_1":
            resource = str(details.get("resource", "a resource")).strip() or "a resource"
            return f"{actor} took {resource} from Taxation."
        if step == "step_2":
            no_bonus = bool(details.get("no_bonus", False))
            resources = [
                resource.strip()
                for resource in str(details.get("resources", "")).split(",")
                if resource.strip()
            ]
            if no_bonus or not resources:
                return f"{actor} took no bonus resource from other majority duties."
            if len(resources) == 1:
                text = resources[0]
            elif len(resources) == 2:
                text = f"{resources[0]} and {resources[1]}"
            else:
                text = ", ".join(resources[:-1]) + f", and {resources[-1]}"
            return f"{actor} took bonus {text} from other majority duties."
        return f"{actor} completed Taxation."

    if event_type is EventType.PIETY_DELTA:
        if "old_piety_position" in details and "new_piety_position" in details:
            old_position = int(details["old_piety_position"])
            new_position = int(details["new_piety_position"])
            if old_position == new_position:
                return None
            delta = new_position - old_position
            if delta > 0:
                return f"{actor} gained {delta} piety and now has {new_position} piety."
            return f"{actor} lost {abs(delta)} piety and now has {new_position} piety."
        amount = int(details.get("piety", 0))
        if amount == 0:
            return None
        if amount > 0:
            return f"{actor} gained {amount} piety."
        return f"{actor} lost {abs(amount)} piety."

    if event_type is EventType.ALMS_PAYMENT:
        credited_silver = details.get("credited_silver")
        credited_wheat = details.get("credited_wheat")
        actual_paid_silver = details.get("actual_paid_silver")
        actual_paid_wheat = details.get("actual_paid_wheat")
        minority_silver_cost = int(details.get("minority_silver_cost", 0))

        if (
            credited_silver is not None
            and credited_wheat is not None
            and actual_paid_silver is not None
            and actual_paid_wheat is not None
        ):
            line = (
                f"{actor} committed {int(credited_silver)} silver and {int(credited_wheat)} wheat "
                "for Give Alms"
            )
            if int(actual_paid_silver) != int(credited_silver) or int(actual_paid_wheat) != int(
                credited_wheat
            ):
                line += (
                    f" and paid {int(actual_paid_silver)} silver and {int(actual_paid_wheat)} wheat"
                )
        else:
            silver = int(details.get("silver", 0))
            wheat = int(details.get("wheat", 0))
            line = f"{actor} paid {silver} silver and {wheat} wheat for Give Alms"
        if minority_silver_cost > 0:
            line += f", including minority cost {minority_silver_cost} silver"
        return f"{line}."

    if event_type is EventType.BUILDING_DONATION:
        building_name = str(details.get("building_name", "")).strip()
        building_id = str(details.get("building_id", "")).strip()
        donated_label = building_name if building_name else _title_words(building_id)
        donation_vp = int(details.get("donation_vp", 0))
        return f"{actor} donated {donated_label} for {donation_vp} victory points."

    if event_type is EventType.BUILDING_CONSTRUCTED:
        building_name = str(details.get("building_name", "")).strip()
        building_id = str(details.get("building_id", "")).strip()
        built_label = building_name if building_name else _title_words(building_id)
        source = str(details.get("source", "market"))
        stone_cost = int(details.get("stone_cost", 0))
        return f"{actor} constructed {built_label} from {source} for {stone_cost} stone."

    if event_type is EventType.BUILDING_HIRED:
        building_name = str(details.get("building_name", "")).strip()
        building_id = str(details.get("building_id", "")).strip()
        hired_label = building_name if building_name else _title_words(building_id)
        source = str(details.get("source", "unknown")).strip()
        source_phrase = "the market" if source == "market" else source
        if bool(details.get("free_with_wagon_yard", False)):
            return f"{actor} hired {hired_label} from {source_phrase} for free with Wagon Yard."

        amount = int(details.get("amount", 0))
        resource = str(details.get("resource", "none")).strip()
        payee = str(details.get("payee", "")).strip()
        if amount <= 0 or not resource or resource == "none":
            return f"{actor} hired {hired_label} from {source_phrase}."

        payment = f" and paid {amount} {resource}"
        if payee and payee not in {"none", source}:
            payment += f" to {'the bank' if payee == 'bank' else payee}"
        return f"{actor} hired {hired_label} from {source_phrase}{payment}."

    if event_type is EventType.ALLOCATION:
        from_pool = _title_words(str(details.get("from_pool", "unknown")))
        to_pool = _title_words(str(details.get("to_pool", "unknown")))
        amount = int(details.get("amount", 0))
        noun = "acolyte" if amount == 1 else "acolytes"
        return f"{actor} moved {amount} {noun} from {from_pool} to {to_pool}."

    if event_type is EventType.ALMS_PROGRESS:
        old_row = int(details.get("old_row", 0))
        new_row = int(details.get("new_row", 0))
        return f"{actor} moved on the Alms table from row {old_row} to row {new_row}."

    if event_type is EventType.ALMS_THRESHOLD_REWARD:
        threshold = int(details.get("threshold", -1))
        reward_key = str(details.get("reward", ""))
        moved = bool(details.get("moved", False))
        if reward_key == "village_to_abbey":
            return (
                f"Crossed Alms row {threshold} and moved 1 serf from Village to Abbey."
                if moved
                else f"Crossed Alms row {threshold}; no Village serf was available to move."
            )
        if reward_key == "abbey_to_city":
            return (
                f"Crossed Alms row {threshold} and moved 1 acolyte from Abbey to City."
                if moved
                else f"Crossed Alms row {threshold}; no Abbey acolyte was available to move."
            )
        if reward_key == "village_to_city":
            return (
                f"Crossed Alms row {threshold} and moved 1 serf from Village to City."
                if moved
                else f"Crossed Alms row {threshold}; no Village serf was available to move."
            )
        reward = _title_words(reward_key) if reward_key else "reward"
        return f"Crossed Alms row {threshold}; reward {reward}."

    if event_type is EventType.ACOLYTE_RECALL:
        duty_position = int(details.get("duty_position", -1))
        recalled = int(details.get("recalled", 0))
        duty = _duty_label_for_players({"duty_position": duty_position}, config)
        noun = "acolyte" if recalled == 1 else "acolytes"
        return f"{actor} recalled {recalled} {noun} from {duty} to City."

    if event_type is EventType.ORDINATION:
        step = str(details.get("step", "")).strip()
        amount = int(details.get("amount", 1))
        if step == "ordain":
            if amount == 1:
                return f"{actor} ordained a serf. It is now an acolyte in the Abbey."
            return f"{actor} ordained {amount} serfs. They are now acolytes in the Abbey."
        if step == "mission":
            if amount == 1:
                return f"{actor} sent an acolyte on a mission. It is now in the City."
            return f"{actor} sent {amount} acolytes on a mission. They are now in the City."
        return None

    if event_type is EventType.SHIP_ADVANCE:
        from_position = int(details.get("from_position", 0))
        to_position = int(details.get("to_position", 0))
        return f"Round end: ship advanced from {from_position} to {to_position}."

    if event_type is EventType.MERCHANT_ADVANCE:
        from_duty = _title_words(str(details.get("from_duty", "unknown")))
        to_duty = _title_words(str(details.get("to_duty", "unknown")))
        return f"Round end: Merchant advanced from {from_duty} to {to_duty}."

    if event_type is EventType.START_PLAYER_TIE_BREAK:
        tied_players = _player_list(str(details.get("tied_players", "")).strip())
        deciding_player = str(details.get("deciding_player", "unknown"))
        current_start_player = str(details.get("current_start_player", "unknown"))
        highest = int(details.get("highest_effective_piety", 0))
        line = (
            "Round end: "
            f"{_join_players(tied_players)} tied on {highest} piety; "
            f"{deciding_player} takes the First Player marker, being the first of them clockwise "
            f"from {current_start_player}."
        )
        return line + _confession_bonus_suffix(details)

    if event_type is EventType.START_PLAYER_MARKER:
        if bool(details.get("tie_break_applied", False)):
            return None
        deciding_player = str(details.get("deciding_player", "unknown"))
        highest = int(details.get("highest_effective_piety", 0))
        runner_up = int(details.get("runner_up_effective_piety", 0))
        runner_up_players = _player_list(str(details.get("runner_up_players", "")).strip())
        line = (
            f"Round end: {deciding_player} took the First Player marker "
            f"with {highest} piety to {_join_possessive_scores(runner_up_players, runner_up)}."
        )
        return line + _confession_bonus_suffix(details)

    if event_type is EventType.START_PLAYER_SELECTION:
        deciding_player = str(details.get("deciding_player", "unknown"))
        selected_player = str(details.get("selected_start_player", "unknown"))
        return f"{deciding_player} chose {selected_player} to begin this round."

    if event_type is EventType.ROUND_END:
        round_number = int(details.get("round", 0))
        return f"Round {round_number} ended."

    if event_type is EventType.BUILDING_BONUS:
        if bool(details.get("player_line_suppressed", False)):
            return None
        line = _building_bonus_for_players(actor, details)
        if line is not None:
            return line
        if _bonus_delta_is_zero(details):
            return None
        if "enabled_route" in details or "skipped_location" in details:
            return None
        # This is an explicit player event. An unfamiliar bonus must not inherit the developer
        # formatter merely because it shares its event type; the corpus guard names the missing
        # player sentence before it can reach the page.
        return None

    if event_type is EventType.SPECIAL_ACTIVITY_BONUS:
        if bool(details.get("player_line_suppressed", False)):
            return None
        line = _special_activity_bonus_for_players(actor, details)
        if line is not None:
            return line
        if _bonus_delta_is_zero(details):
            return None
        return None

    if event_type in PLAYER_EVENT_FALLBACK_TYPES:
        return format_event(event, config)
    raise AssertionError(f"Unhandled player event formatting branch for {event_type.value}")
