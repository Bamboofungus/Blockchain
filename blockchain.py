import hashlib
import json
from time import time
from uuid import uuid4
from urllib.parse import urlparse

import requests
from flask import Flask, jsonify, request

'''
Base code created following tutorial:
https://hackernoon.com/learn-blockchains-by-building-one-117428612f46

Interact with by using POSTMAN to send requests to http://0.0.0.0:5000/
after running

TODO 
- create app for interacting with blockchain
- implement Transaction Validation Mechanism
- implement some market cap on coin
- create some hub for nodes to meet?
- implement HashCash for mining?
- speed up code using Timer
- check security
'''

class Blockchain(object):
    def __init__(self):
        self.chain = []
        self.current_transactions = []
        self.nodes = set()
        self.new_block(previous_hash=1, proof=100)
    
    def register_node(self, address: str):
        """
        Add a new node to the list of nodes
        address: Address of node
        """

        parsed_url = urlparse(address)
        self.nodes.add(parsed_url.netloc)
        
    def new_block(self, proof: int, previous_hash=None) -> dict:
        '''
        Creates a new Block and adds it to the chain

        transactions: List of current pending transactions
        proof: given by Proof of Work algorithm (proof_of_work())
        previous_hash(Optional): String hash of previous Block
        '''
        block = {
            'index': len(self.chain) + 1,
            'timestamp': time(),
            'transactions': self.current_transactions,
            'proof': proof,
            'previous_hash': previous_hash or self.hash(self.chain[-1])
        }
        # Reset pending transactions
        self.current_transactions = []

        self.chain.append(block)
        return block

    def new_transaction(self, sender: str, recipient: str, amount: int) -> int:
        # Adds a new transaction to the list of pending transactions
        self.current_transactions.append({
            'sender': sender,
            'recipient': recipient,
            'amount': amount,
        })
        # Returns index of block to be mined
        return self.last_block['index'] + 1
        
    @staticmethod
    def hash(block: dict) -> str:
        # Hashes a Block with SHA-256

        # Orders by keys, then reencodes
        block_string = json.dumps(block, sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()

    @property
    def last_block(self):
        # Returns the last Block in the chain
        return self.chain[-1]

    def proof_of_work(self, last_proof: int) -> int:
        '''
        Finds number 'p' such that hash(p*last_proof) contains
        4 leading zeroes. 

        TODO Maybe replace with implementation of HashCash later?
        '''
        proof = 0
        while self.valid_proof(last_proof, proof) is False:
            proof += 1
        return proof

    @staticmethod
    def valid_proof(last_proof: int, proof: int) -> bool:
        """
        Validates the Proof: Does hash(last_proof, proof) contain 4 leading zeroes?
        """

        guess = f'{last_proof}{proof}'.encode()
        guess_hash = hashlib.sha256(guess).hexdigest()
        return guess_hash[:4] == "0000"

    def valid_chain(self, chain: list) -> bool:
        """
        Determine if a given blockchain is valid by comparing to this node's chain
        """
        previous_block = chain[0]
        current_index = 1

        while current_index < len(chain):
            block = chain[current_index]
            print(f'{previous_block}')
            print(f'{block}')
            print("\n-----------\n")

            if block['previous_hash'] != self.hash(previous_block):
                return False
            
            # Check if proof is correct
            if not self.valid_proof(previous_block['proof'], block['proof']):
                return False
            
            previous_block = block
            current_index += 1

        return True

    def resolve_conflicts(self) -> bool:
        """
        Resolve conflicts in network, return boolean depending on if chain
        was replaced
        """

        neighbours = self.nodes
        new_chain = None

        min_length = len(self.chain)

        # Retrieve chains from added nodes
        for node in neighbours:
            response = requests.get(f'http://{node}/chain')

            if response.status_code == 200:
                length = response.json()['length']
                chain = response.json()['chain']

                # Check if longer and valid
                if length > min_length and self.valid_chain(chain):
                    min_length = length
                    new_chain = chain

        #Replace this nodes chain
        if new_chain:
            self.chain = new_chain
            return True
        return False

            
    
# Instantiate our Node
app = Flask(__name__)

# Generate a globally unique address for this node
node_identifier = str(uuid4()).replace('-', '')

# Instantiate the Blockchain
blockchain = Blockchain()

@app.route('/mine', methods=['GET'])
def mine():
    last_block = blockchain.last_block
    last_proof = last_block['proof']
    proof = blockchain.proof_of_work(last_proof)

    # Reward miner with one coin
    # "0" for sender signifies this node mined new coin
    blockchain.new_transaction(
        sender="0",
        recipient=node_identifier,
        amount=1,
    )

    #Add new block to chain
    previous_hash = blockchain.hash(last_block)
    block = blockchain.new_block(proof, previous_hash)

    response = {
        'message': "New Block Forged",
        'index': block['index'],
        'transactions': block['transactions'],
        'proof': block['proof'],
        'previous_hash': block['previous_hash'],
    }
    return jsonify(response), 200

@app.route('/transactions/new', methods=['POST'])
def new_transaction():
    values = request.get_json()

    # Check payload
    required = ['sender', 'recipient', 'amount']
    if not all(k in values for k in required):
        return 'Missing values', 400
    
    # Create a new Transaction
    index = blockchain.new_transaction(
        values['sender'], values['recipient'], values['amount'])
        
    response = {'message': f'Transaction will be added to Block {index}'}
    return jsonify(response), 201


@app.route('/chain', methods=['GET'])
def full_chain():
    response = {
        'chain': blockchain.chain,
        'length': len(blockchain.chain),
    }
    return jsonify(response), 200


@app.route('/nodes/register', methods=['POST'])
def register_nodes():
    values = request.get_json()

    # Validate payload
    nodes = values.get('nodes')
    if nodes is None:
        return "Error: Please supply a valid list of nodes", 400

    for node in nodes:
        blockchain.register_node(node)

    response = {
        'message': 'New nodes have been added',
        'total_nodes': list(blockchain.nodes),
    }
    return jsonify(response), 201


@app.route('/nodes/resolve', methods=['GET'])
def consensus():
    replaced = blockchain.resolve_conflicts()

    if replaced:
        response = {
            'message': 'Our chain was replaced',
            'new_chain': blockchain.chain
        }
    else:
        response = {
            'message': 'Our chain is authoritative',
            'chain': blockchain.chain
        }

    return jsonify(response), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
