# Masternode Vote Monitor
### Requirements
- pystratis 1.1.0.0
- StratisFullNode release/1.1.0.0

Python dependencies
- python-decouple
- asyncio
- discord (for bot)

### Usage
1. Create a .env file in the same directory as mn_vote_monitor.py with the following keys:
 - SDA_CONTRACT_ADDRESS='CbtYboKjnk7rhNbEFzn94UZikde36h6TCb'
 - SENDER_ADDRESS='your-cirrus-address-here'
 - **For discord bot only**
   - DISCORD_TOKEN='discord-oath2-token'
   - DISCORD_GUILD='the-stratisplatform-discord-server-id'
   - DISCORD_CHANNEL='the-channel-id-for-monitoring'

```python
python mn_vote_monitor.py {--bot}
```

### TODO
- Finish bot integration