
# This is a simple implementation to demonstrate the concept of a blockchain
# It is not a real blockchain, but it is enough to demonstrate the concept
# The main building blocks are here so you can see how a blockchain works even if it has not yet been covered in the lecture
# The blockchain consists of blocks, each block has a parent block, except for the genesis block
# The longest chain is considered the majority consensus for the blockchain
# The blockchain has a method to check random access to the critical section
# this would be Proof of work (PoW) in a real blockchain or some other consensus mechanism


import random
import time

class Block:
    def __init__(self, index, parent_block_hash, data):
        self.parent_block_hash = parent_block_hash
        self.index = index
        self.data = data
        self.hash = hash((self.index, self.data, self.parent_block_hash))

    def __hash__(self):
        return self.hash


GENESIS_BLOCK_HASH = 42

class GenesisBlock(Block):
    def __init__(self):
        self.index = 0
        self.hash = 42
        self.data = None

    def __hash__(self):
        return self.hash


class Blockchain:

    def __init__(self):
        self.genesis_block = GenesisBlock()
        self.blocks = {}
        self.blocks[self.genesis_block.hash] = self.genesis_block
        assert self.has_block(GENESIS_BLOCK_HASH)

        self.highest_index = 0
        self.highest_block = self.genesis_block


    # This method allos random access to the CS
    # Generates a random number between 0 and 2^(log_difficulty), only if this number turns out to be 0, the access is granted
    # The higher the log_difficulty, the less likely the access is granted
    # The sleep_s parameter is used to simulate the time it takes to check the access (just like finding the correct PoW)
    def check_rand_access(self, log_difficulty=0) -> bool:
        # get a random number between 0 and 100
        rand_num = random.randint(0, 2**log_difficulty)

        time.sleep(0.01)

        return rand_num == 0

    def get_highest_index(self):
        return self.highest_index

    def get_highest_block_hash(self):
        return self.highest_block.hash

    def has_block(self, parent_block_hash):
        return parent_block_hash in self.blocks

    def add_block(self, data, parent_block_hash=GENESIS_BLOCK_HASH):
        if not self.has_block(parent_block_hash):
            return None

        parent_block = self.blocks[parent_block_hash]
        idx = parent_block.index + 1
        block = Block(idx, parent_block_hash, data)
        self.blocks[block.hash] = block

        # ever increasing index
        if idx > self.highest_index:
            self.highest_index = idx
            self.highest_block = block

        return block.hash

    def get_block(self, block_hash):
        return self.blocks.get(block_hash, None)

    def get_hashes_recursive(self, block_hash):
        block = self.get_block(block_hash)
        assert block is not None

        if block.index == 0:
            return []

        parent_hashes = self.get_hashes_recursive(block.parent_block_hash)
        return parent_hashes + [block.hash]

    def get_data_recursive(self, block_hash):
        block = self.get_block(block_hash)
        assert block is not None

        if block.index == 0:
            return []

        parent_data = self.get_data_recursive(block.parent_block_hash)
        return parent_data + [block.data]

if __name__ == "__main__":
    blockchain = Blockchain()

    block1 = blockchain.add_block("hello")
    block2 = blockchain.add_block("world") # these blocks will not be connected!
    print(blockchain.get_data_recursive(block1))
    print(blockchain.get_data_recursive(block2))

    block_with_missing_parent = blockchain.add_block("!", 123) # this parent block does not exist!
    print(block_with_missing_parent) # this will print None!

    block3 = blockchain.add_block("hello")
    block4 = blockchain.add_block("world", block3) # these blocks will actually be connected now!
    block5 = blockchain.add_block("!", block4)
    print(blockchain.get_data_recursive(block5))

    print(blockchain.get_highest_index())
    print(blockchain.get_highest_block_hash())

    print(sum([blockchain.check_rand_access(14) for i in range(100 * 4 * 10)]))




