import sys
import json
import hashlib
import requests
from time import time
from urllib.parse import urlparse
from uuid import uuid4
from flask import Flask, jsonify, request


class Blockchain():
    ''' defines a block chain on one machine '''
    def __init__(self):
        self.chain = []
        self.current_trxs = []
        self.nodes = set()
        self.new_block(previous_hash=1, proof=100)

    def new_block(self, proof, previous_hash=None):
        ''' create a new block '''
        block = {
            'index': len(self.chain) + 1,
            'timestamp': time(),
            'trxs': self.current_trxs,
            'proof': proof,
            'previous_hash': previous_hash or self.hash(self.chain[-1]),
        }

        self.current_trxs = []

        self.chain.append(block)
        return block

    def new_trx(self, sender, recipient, amount):
        ''' add a new trx to the mempool '''
        self.current_trxs.append({"sender":sender, "recipient":recipient,
                                 "amount":amount})

        return self.last_block['index'] + 1

    def register_node(self, address):
        parsed_url = urlparse(address)
        self.nodes.add(parsed_url.netloc)

    def valid_chain(self, chain):
        """ check if the chain is valid """
        last_block = chain[0]
        current_index = 1
        while current_index < len(chain):
            block = chain[current_index]
            if block['previous_hash'] != self.hash(last_block):
                return False

            if not self.valid_proof(last_block['proof'], block['proof']):
                return False

            last_block = block 
            current_index += 1

        return True

    def resolve_conflicts(self):
        """ check all nodes and selects the best chain """
        neighbours = self.nodes
        new_chain = None

        max_lenght = len(self.chain)
        for node in neighbours:
            response = requests.get(f'http://{node}/chain')
            if response.status_code == 200:
                length = response.json()['length']
                chain = response.json()['chain']
                if length > max_lenght and self.valid_chain(chain):
                    max_lenght = length
                    new_chain = chain

        if new_chain:
            self.chain = new_chain
            return True
        
        return False

    @staticmethod
    def hash(block):
        ''' hash a block '''
        block_string = json.dumps(block, sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()

    @property
    def last_block(self):
        ''' return last block '''
        return self.chain[-1]

    @staticmethod
    def valid_proof(last_proof, proof):
        ''' checks if this proof is fine or not '''
        this_proof = f'{proof}{last_proof}'.encode()
        this_proof_hash = hashlib.sha256(this_proof).hexdigest()
        return this_proof_hash[:4] == '0000'


    def proof_of_work(self, last_proof):
        ''' shows that the work is done '''
        proof = 0
        while self.valid_proof(last_proof, proof) is False:
            proof += 1

        return proof

app = Flask(__name__)

node_id = str(uuid4())

blockchain = Blockchain()

@app.route('/mine')
def mine():
    ''' this will mine one block and
    will add it to the chain
    '''
    last_block = blockchain.last_block
    last_proof = last_block['proof']
    proof = blockchain.proof_of_work(last_proof)

    blockchain.new_trx(sender="0", recipient=node_id, amount=50)
    previous_hash = blockchain.hash(last_block)
    block = blockchain.new_block(proof, previous_hash)
    
    res = {
        'message': 'new block created.',
        'index': block['index'],
        'trxs': block['trxs'],
        'proof': block['proof'],
        'previous_hash': block['previous_hash'],
    }

    return jsonify(res), 200

@app.route('/trxs/new', methods=['POST'])
def new_trx():
    ''' will add a new trx by getting sender, recipient, amount'''
    values = request.get_json()
    this_block = blockchain.new_trx(values['sender'], values['recipient'], values['amount'])
    res = {'message': f'will be added to block {this_block}'} 
    return jsonify(res), 201

@app.route('/chain')
def full_chain():
    ''' returns the full chain '''
    res = {
        'chain': blockchain.chain,
        'length': len(blockchain.chain),
    }
    return jsonify(res), 200

@app.route('/nodes/register', methods=['POST'])
def register_node():
    values = request.get_json()


    nodes = values.get('nodes')
    for node in nodes:
        blockchain.register_node(node)

    res = {'message': 'nodes added',
            'total_nodes': list(blockchain.nodes)    
        }
    return jsonify(res), 201

@app.route('/nodes/resolve')
def consensus():
    replaced = blockchain.resolve_conflicts()
    if replaced:
        res = {'message': 'replaced!',
                'new_chain': blockchain.chain,
            }
    
    else :
        res = {'message': 'Im the best',
                'chain': blockchain.chain,
            }

    return jsonify(res), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=sys.argv[1])
