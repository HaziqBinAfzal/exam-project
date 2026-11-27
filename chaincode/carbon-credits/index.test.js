'use strict';

const assert = require('node:assert/strict');
const test = require('node:test');
const { contracts: [CarbonCredits] } = require('./index');

const fingerprint = 'a'.repeat(64);
const issuance = ['CC-101', '10', 'REGISTRY-A', 'A-101', 'ORIGIN-101'];
const approval = ['ORIGIN-101', 'REGISTRY-A', 'A-101', '10', 'DEMO-MRV-V1', fingerprint];

function setup() {
    const state = new Map();

    function context(msp, txId) {
        return {
            clientIdentity: { getMSPID: () => msp },
            stub: {
                createCompositeKey: (kind, parts) => JSON.stringify([kind, ...parts]),
                getState: async key => state.get(key) ?? Buffer.alloc(0),
                putState: async (key, bytes) => { state.set(key, Buffer.from(bytes)); },
                getTxID: () => txId,
            },
        };
    }

    return {
        contract: new CarbonCredits(),
        issuer: context('Org1MSP', 'issuer-tx'),
        verifier: context('Org2MSP', 'verifier-tx'),
    };
}

test('the issuer cannot approve its own credit', async () => {
    const { contract, issuer } = setup();
    await assert.rejects(contract.ApproveOrigin(issuer, ...approval), /Only the verifier/);
});

test('issuance requires an approval and a matching quantity', async () => {
    const { contract, issuer, verifier } = setup();
    await assert.rejects(contract.IssueCredit(issuer, ...issuance), /no verifier approval/);
    await contract.ApproveOrigin(verifier, ...approval);
    await assert.rejects(
        contract.IssueCredit(issuer, 'CC-101', '11', ...issuance.slice(2)),
        /does not match the approval/,
    );
});

test('the verifier cannot approve an unsupported methodology', async () => {
    const { contract, verifier } = setup();
    await assert.rejects(
        contract.ApproveOrigin(verifier, ...approval.slice(0, 4), 'UNSUPPORTED', fingerprint),
        /Unsupported verification methodology/,
    );
});

test('issuance stores the verifier proof and blocks a duplicate origin across registries', async () => {
    const { contract, issuer, verifier } = setup();
    await contract.ApproveOrigin(verifier, ...approval);
    await contract.IssueCredit(issuer, ...issuance);

    const credit = await contract.ReadCredit(verifier, 'CC-101');
    assert.equal(credit.status, 'ISSUED');
    assert.equal(credit.verification.verifierMsp, 'Org2MSP');
    assert.equal(credit.verification.approvalTxId, 'verifier-tx');
    assert.equal(credit.verification.evidenceSha256, fingerprint);

    await assert.rejects(
        contract.IssueCredit(issuer, 'CC-102', '10', 'REGISTRY-B', 'B-102', 'ORIGIN-101'),
        /Origin ORIGIN-101 is already linked to a credit/,
    );
});
