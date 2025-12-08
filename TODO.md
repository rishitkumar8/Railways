# Fix Stale Closure in TrainMap Animation

## Tasks
- [x] Fix animation useEffect to read fresh trains and stations from store inside animate function
- [x] Update getTrainPosition to read fresh stations from store
- [x] Optimize updateTrainsOnMap to only add/remove markers as needed instead of recreating all
- [x] Remove trains and stations from animation useEffect dependencies
- [x] Test animation with multiple trains to ensure updates work
- [x] Verify performance improvements with marker management
