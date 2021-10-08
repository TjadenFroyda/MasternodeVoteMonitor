import argparse
import asyncio
import discord
from decouple import config
from typing import Dict, List, Tuple, Union
from pystratis.nodes import CirrusMasterNode, CirrusNode
from pystratis.core.types import Address, Money
from pystratis.core import PubKey, SmartContractParameter, SmartContractParameterType
from pystratis.core.networks import CirrusMain


def find_whitelisted_federation_addresses(
        node: Union[CirrusNode, CirrusMasterNode],
        payout_address_list: List[str]) -> List[str]:
    """Finds whitelisted addresses for the SDA DAO contract.

    Args:
        node (CirrusNode, CirrusMasterNode): The node.
        payout_address_list (List[str]): The list of Cirrus addresses that have received payouts.

    Returns:
        List[str]: A list of cirrus addresses that are whitelisted for the StratisDAO smart contract.

    """
    federation_addresses = []
    for address in payout_address_list:
        address = Address(address=address, network=CirrusMain())
        is_whitelisted = check_if_address_is_dao_whitelisted(node=node, address=address)
        if is_whitelisted:
            federation_addresses.append(str(address))
    return federation_addresses


def get_current_federation_pubkeys(node: Union[CirrusNode, CirrusMasterNode]) -> List[str]:
    """Get the current federation pubkeys.

    Args:
        node (CirrusNode, CirrusMasterNode): The node.

    Returns:
        List[str]: A list of pubkeys representing the current federation.
    """
    fed_members = node.federation.members()
    return [str(x.pubkey) for x in fed_members]


def get_pubkey_and_address_for_height(
        node: Union[CirrusNode, CirrusMasterNode],
        height: int) -> Tuple[PubKey, Address]:
    """Extract the pubkey and address at the specified block height.

    Args:
        node (CirrusNode, CirrusMasterNode): The node.
        height (int): The specified height.

    Returns:
        Tuple[Pubkey, Address]: The pubkey and address pair of the block producer at given height.
    """
    # PubKey can be directly obtained from the api.
    pubkey = node.federation.miner_at_height(block_height=height)
    # The address must be extracted from the block.
    # First get the block at the specified height.
    block_hash = node.consensus.get_blockhash(height=height)
    block = node.blockstore.block(block_hash=block_hash)
    # The address will typically be in the first transaction.
    for transaction in block.transactions:
        # Correct vout is typically the first
        for vout in transaction.vout:
            # Verify that the vout is a script_pubkey with the correct type.
            script_pubkey = vout.script_pubkey
            if script_pubkey.type in ['pubkey', 'pubkeyhash']:
                # Extract the address.
                address = Address(address=script_pubkey.addresses[0], network=CirrusMain())
                return pubkey, address


def get_address_to_fedkey_map(
        node: Union[CirrusNode, CirrusMasterNode],
        lookback: int = 500) -> Dict[str, str]:
    """Returns a map from address to fedkey.

    Args:
        node (CirrusNode, CirrusMasterNode): The node.
        lookback (int): How many blocks to lookback from tip.

    Returns:
        Dict[str, str]: A dictionary mapping cirrus address to fedkey.
    """
    fedkey_to_address_map = {}
    current_block_height = node.blockstore.get_block_count()
    starting_block_height = current_block_height - lookback
    # Iterates from lookback to the current tip and extracts pubkey/address pairs.
    for i in range(starting_block_height, current_block_height):
        pubkey, address = get_pubkey_and_address_for_height(node=node, height=i)
        # Only add to dictionary if not already in dictionary.
        if pubkey is not None and str(pubkey) not in fedkey_to_address_map:
            fedkey_to_address_map[str(pubkey)] = address
    # Reverse the mapping.
    address_to_fedkey_map = {str(v): k for k, v in fedkey_to_address_map.items()}
    return address_to_fedkey_map


def check_if_address_is_dao_whitelisted(
        node: Union[CirrusNode, CirrusMasterNode],
        address: Union[Address, str]) -> bool:
    """Uses local_call to check if given address is whitelisted.

    Args:
        node (CirrusNode, CirrusMasterNode): The node.
        address (Address, str): The address to check.

    Returns:
        bool: If True, the address is whitelisted.
    """
    response = node.smart_contracts.local_call(
        contract_address=Address(address=config('SDA_CONTRACT_ADDRESS'), network=CirrusMain()),
        method_name='IsWhitelisted',
        amount=Money(0),
        gas_price=100,
        gas_limit=250000,
        sender=Address(address=config('SENDER_ADDRESS'), network=CirrusMain()),
        block_height=None,
        parameters=[SmartContractParameter(value_type=SmartContractParameterType.Address, value=address)]
    )
    return response.return_obj


def get_address_proposal_vote(
        node: Union[CirrusNode, CirrusMasterNode],
        proposal_id: int,
        address: Union[Address, str]) -> Union[int, None]:
    """Uses local_call to check vote for specified proposal.

    Args:
        node (CirrusNode, CirrusMasterNode): The node.
        proposal_id (int): The proposal id to check.
        address (Address, str): The cirrus address to check

    Returns:
        int: A value representing nonvote, no, and yes votes, respectively.
    """
    response = node.smart_contracts.local_call(
        contract_address=Address(address=config('SDA_CONTRACT_ADDRESS'), network=CirrusMain()),
        method_name='GetVote',
        amount=Money(0),
        gas_price=100,
        gas_limit=250000,
        sender=Address(address=config('SENDER_ADDRESS'), network=CirrusMain()),
        block_height=None,
        parameters=[
            SmartContractParameter(value_type=SmartContractParameterType.UInt32, value=proposal_id),
            SmartContractParameter(value_type=SmartContractParameterType.Address, value=str(address))
        ]
    )
    return response.return_obj


def get_last_proposal_id(node: Union[CirrusNode, CirrusMasterNode]) -> int:
    """Uses local_call to check id of last proposal.

    Args:
        node (CirrusNode, CirrusMasterNode): The node.

    Returns:
        int: The last proposal id.
    """
    response = node.smart_contracts.local_call(
        contract_address=Address(address=config('SDA_CONTRACT_ADDRESS'), network=CirrusMain()),
        method_name='LastProposalId',
        amount=Money(0),
        gas_price=100,
        gas_limit=250000,
        sender=Address(address=config('SENDER_ADDRESS'), network=CirrusMain()),
        block_height=None,
        parameters=[]
    )
    return response.return_obj


def get_last_completed_proposal_id(
        node: Union[CirrusNode, CirrusMasterNode],
        highest_proposal_id: int) -> int:
    """Uses local_call to check id of last completed proposal.

    Args:
        node (CirrusNode, CirrusMasterNode): The node.
        highest_proposal_id (int): The highest proposal id.

    Returns:
        int: The last proposal id.
    """
    best_completed_proposal_id = 1
    current_block_height = node.blockstore.get_block_count()
    for index in range(highest_proposal_id):
        proposal_id = index + 1
        ending_height = get_proposal_ending_height(node=node, proposal_id=proposal_id)
        if ending_height < current_block_height and ending_height != 0:
            best_completed_proposal_id = proposal_id
    return best_completed_proposal_id


def get_proposal_ending_height(
        node: Union[CirrusNode, CirrusMasterNode],
        proposal_id: int) -> int:
    """Gets the proposal ending height.

    Args:
        node (CirrusNode, CirrusMasterNode): The node.
        proposal_id (int): The proposal id.

    Returns:
        int: The ending height for the given proposal.
    """
    response = node.smart_contracts.local_call(
        contract_address=Address(address=config('SDA_CONTRACT_ADDRESS'), network=CirrusMain()),
        method_name='GetVotingDeadline',
        amount=Money(0),
        gas_price=100,
        gas_limit=250000,
        sender=Address(address=config('SENDER_ADDRESS'), network=CirrusMain()),
        block_height=None,
        parameters=[
            SmartContractParameter(value_type=SmartContractParameterType.UInt32, value=proposal_id)
        ]
    )
    return response.return_obj
    

def tabulate_fed_member_votes(
        node: Union[CirrusNode, CirrusMasterNode],
        current_whitelisted_fed_addresses: List[str],
        num_sda_proposals: int) -> dict:
    """Tabulates the votes based on payout address.

    Args:
        node (CirrusNode, CirrusMasterNode): The node.
        current_whitelisted_fed_addresses (List[str]): A list of currently DAO whitelisted cirrus addresses.
        num_sda_proposals (int): The number of compleded sda proposals.

    Returns:
        dict: A dictionary with keys "Address": {"NoVote":[], "No":[], and "Yes":[]}, each populated with a list of proposals_ids for each vote type.
    """
    fed_member_votes = {}
    for address in current_whitelisted_fed_addresses:
        # Create the dictionary substructure.
        fed_member_votes[address] = {'NoVote': [], 'No': [], 'Yes': []}
        for index in range(num_sda_proposals):
            proposal_id = index + 1
            # Retrieve the vote
            vote = get_address_proposal_vote(
                node=node, 
                proposal_id=proposal_id,
                address=address
            )
            # Map the enum to add to the appropriate list.
            if vote == 0:
                fed_member_votes[address]['NoVote'].append(proposal_id)
            elif vote == 1:
                fed_member_votes[address]['No'].append(proposal_id)
            elif vote == 2:
                fed_member_votes[address]['Yes'].append(proposal_id)
    return fed_member_votes


def filter_eligible_fedkeys(
        node: Union[CirrusNode, CirrusMasterNode],
        fed_member_votes: dict,
        address_to_fedkey_map: dict,
        best_proposal_id: int) -> Dict[str, str]:
    """Filters eligible fedkeys so that only those who have been registered before the end of the third to last proposal are counted.

    Args:
        node (CirrusNode, CirrusMasterNode): The node.
        fed_member_votes (dict): A dictionary of federation member votes.
        address_to_fedkey_map (dict): A dictionary mapping address to fedkey.
        best_proposal_id (int): The highest completed proposal id.

    Returns:
        dict: A filtered dictionary of federation member votes.
    """
    # Find the ending height for the 3rd to last proposal.
    ending_height_for_third_last_proposal = get_proposal_ending_height(
        node=node,
        proposal_id=best_proposal_id-2
    )
    # Use the API to get the federation at that height.
    federation_at_end_of_third_last_proposal = node.federation.federation_at_height(ending_height_for_third_last_proposal)
    federation_at_end_of_third_last_proposal = [str(x) for x in federation_at_end_of_third_last_proposal]
    # Filter out keys not in the federation at that time.
    filtered_fed_member_votes = {k: v for k, v in fed_member_votes.items() if address_to_fedkey_map[k] in federation_at_end_of_third_last_proposal}
    return filtered_fed_member_votes


def get_nonvoting_fedkeys_in_last_3_proposals(
        address_to_fedkey_map: dict,
        fed_member_votes: dict,
        best_proposal_id: int) -> List[str]:
    """Returns the eligible fedkeys that haven't voted for the last 3 proposals.

    Args:
        address_to_fedkey_map (dict): A dictionary mapping address to fedkey.
        fed_member_votes (dict): A dictionary of federation member votes.
        best_proposal_id (int): The highest completed proposal id.

    Returns:
        List[str]: A list of nonvoting pubkeys for last 3 proposals.
    """
    return [
        address_to_fedkey_map[k] for k, v in fed_member_votes.items() if best_proposal_id in v['NoVote'] and best_proposal_id-1 in v['NoVote'] and best_proposal_id-2 in v['NoVote']
    ]


def markdown_format_output(nonvoting_fedkeys: list) -> str:
    """Markdown format the output.

    Args:
        nonvoting_fedkeys (List[str]): A list of non-voting pubkeys.

    Returns:
        str: Markdown formatted output, sorted by pubkey.
    """
    output = ['**The following fedkeys were eligible and have not voted for the last 3 completed proposal votes:**']
    nonvoting_fedkeys = [f'- {fedkey}' for fedkey in nonvoting_fedkeys]
    nonvoting_fedkeys.sort()
    output.extend(nonvoting_fedkeys)
    return "\n".join(output)


def run_vote_monitor() -> str:
    """The vote monitoring algorithm.

    Notes:
        This alogrithm will miss any fedkeys that have not mined a block in the lookback interval.
        For increased sensitivity, increase the lookback.

    Returns:
        str: Markdown formatted output, sorted by pubkey.
    """
    node = CirrusMasterNode()

    # Get the current number of federation members
    num_fed_members = len(get_current_federation_pubkeys(node))

    # Get address to fedkey mapping
    address_to_fedkey_map = get_address_to_fedkey_map(node, lookback=num_fed_members*3)

    # Get the number of sda proposals (1-indexed)
    highest_proposal_id = get_last_proposal_id(node=node)
    num_sda_proposals = get_last_completed_proposal_id(node=node, highest_proposal_id=highest_proposal_id)

    # Get the current whitelisted federation addresses
    current_whitelisted_fed_addresses = find_whitelisted_federation_addresses(
        node=node,
        payout_address_list=[k for k in address_to_fedkey_map.keys()]
    )

    # Iterate through each proposal to tabulate current federation member voting history
    fed_member_votes = tabulate_fed_member_votes(
        node=node,
        current_whitelisted_fed_addresses=current_whitelisted_fed_addresses,
        num_sda_proposals=num_sda_proposals
    )

    # Filter in only eligible voters (registered during all 3 proposals)
    fed_member_votes = filter_eligible_fedkeys(
        node=node,
        fed_member_votes=fed_member_votes,
        address_to_fedkey_map=address_to_fedkey_map,
        best_proposal_id=num_sda_proposals
    )

    # Get the non-voters on the last 3 proposals
    nonvoting_fedkeys = get_nonvoting_fedkeys_in_last_3_proposals(
        address_to_fedkey_map=address_to_fedkey_map,
        fed_member_votes=fed_member_votes,
        best_proposal_id=num_sda_proposals
    )

    return markdown_format_output(nonvoting_fedkeys=nonvoting_fedkeys)


class DiscordClient(discord.Client):
    async def on_ready(self):
        print(f'{self.user} has connected to Discord!')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--bot", help="Run bot")
    args = parser.parse_args()
    # TODO - Bot is unfinished
    if args.bot:
        client = DiscordClient()
        client.run(config('DISCORD_TOKEN'))

        channel = client.get_channel(config('DISCORD_CHANNEL'))

        while True:
            msg = run_vote_monitor()
            channel.send(msg)
            asyncio.sleep(60 * 60 * 24 * 7)
    else:
        print(run_vote_monitor())
