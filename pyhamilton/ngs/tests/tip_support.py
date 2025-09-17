from pyhamilton import HamiltonInterface, LayoutManager, Tip96, layout_item, Plate96, TrackedTips, tip_support_pickup_columns, TipSupportTracker

lmgr = LayoutManager('PacBio_MultiPlexLibraryPrepDeck_v1.2.lay')
tip_support_resource = layout_item(lmgr, Tip96, 'TipSupport_0001')

tracked_tips_50uL = TrackedTips.from_prefix(
                        tracker_id="TIP_50uLF_L",
                        volume_capacity=50,
                        prefix="TIP_50uLF_L",
                        count=8,
                        tip_type=Tip96, 
                        lmgr=lmgr)

tip_support = TipSupportTracker(tip_support_resource)  

with HamiltonInterface(simulating=False, windowed=True) as ham_int:
    ham_int.initialize()
    for _ in range(3):
        tip_support_pickup_columns(ham_int, tracked_tips_50uL, tip_support_tracker=tip_support, num_columns=4)
        ham_int.tip_eject_96()