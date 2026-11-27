'use strict';

const { Contract } = require('fabric-contract-api');

class CarbonCredits extends Contract {
    async IssueCredit(ctx, creditId, quantityText) {
        if (ctx.clientIdentity.getMSPID() !== 'Org1MSP') {
            throw new Error('Only the registry organization can issue credits');
        }
        if (!/^CC-[A-Z0-9-]{1,40}$/.test(creditId)) {
            throw new Error('Invalid credit ID');
        }

        const quantity = Number(quantityText);
        if (!/^[1-9][0-9]*$/.test(quantityText) || !Number.isSafeInteger(quantity)) {
            throw new Error('Quantity must be a positive whole number');
        }

        const key = ctx.stub.createCompositeKey('credit', [creditId]);
        const existing = await ctx.stub.getState(key);
        if (existing.length > 0) {
            throw new Error(`Credit ${creditId} already exists`);
        }

        const credit = {
            creditId,
            quantityTonnesCO2e: quantity,
            ownerMsp: ctx.clientIdentity.getMSPID(),
            status: 'ISSUED',
        };
        await ctx.stub.putState(key, Buffer.from(JSON.stringify(credit)));
        return credit;
    }

    async ReadCredit(ctx, creditId) {
        const key = ctx.stub.createCompositeKey('credit', [creditId]);
        const record = await ctx.stub.getState(key);
        if (record.length === 0) {
            throw new Error(`Credit ${creditId} was not found`);
        }
        return JSON.parse(record.toString('utf8'));
    }
}

module.exports.contracts = [CarbonCredits];
