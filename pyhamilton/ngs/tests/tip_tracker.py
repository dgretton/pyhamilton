from pyhamilton import (HamiltonInterface, LayoutManager, Tip96, TrackedTips, resource_list_with_prefix, 
                        Tip96, Plate96, ResourceType, tip_pick_up, DeckResource, tracked_tip_pick_up, tracked_tip_pick_up_96)

from typing import List, Tuple

lmgr = LayoutManager('PacBio_MultiPlexLibraryPrepDeck_v1.2.lay')

#tips_50uL = resource_list_with_prefix(lmgr, 'TIP_50uLF_L_000', Tip96, 5) # Need zero padding for the resource names

tips_50uL_tracker = TrackedTips.from_prefix(
    tracker_id="TIP_50uLF_L",
    prefix="TIP_50uLF_L",
    count=8,
    lmgr=lmgr,
    tip_type=Tip96,
    reset=False  # Reset the tracker state
)

#tips = tips_50uL_tracker.fetch_next(5)
#print(f'Fetched tips: {tips}')

with HamiltonInterface(windowed=True) as ham_int:
    ham_int.initialize()
    tracked_tip_pick_up(ham_int, tips_50uL_tracker, 5)
