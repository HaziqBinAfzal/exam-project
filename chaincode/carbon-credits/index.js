'use strict';

const { Contract } = require('fabric-contract-api');

class CarbonCredits extends Contract {
    async IssueCredit(ctx, creditId, quantityText, registry, registryRef, originId) {
        if (ctx.clientIdentity.getMSPID() !== 'Org1MSP') {
            throw new Error('Only the registry organization can issue credits');
        }
        if (!/^CC-[A-Z0-9-]{1,40}$/.test(creditId)) {
            throw new Error('Invalid credit ID');
        }

        if (!['REGISTRY-A', 'REGISTRY-B'].includes(registry)) {
            throw new Error('Registry is outside the demo allowlist');
        }
        if (!/^[A-Z0-9-]{1,64}$/.test(registryRef) ||
            !/^[A-Z0-9-]{1,64}$/.test(originId)) {
            throw new Error('Registry reference and origin ID must use the normalized format');
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

        const originKey = ctx.stub.createCompositeKey('origin', [originId]);
        if ((await ctx.stub.getState(originKey)).length > 0) {
            throw new Error(`Origin ${originId} is already linked to a credit`);
        }

        const registryKey = ctx.stub.createCompositeKey('registry-ref', [registry, registryRef]);
        if ((await ctx.stub.getState(registryKey)).length > 0) {
            throw new Error(`Registry reference ${registry}/${registryRef} is already linked to a credit`);
        }

        const credit = {
            creditId,
            registry,
            registryRef,
            originId,
            quantityTonnesCO2e: quantity,
            ownerMsp: ctx.clientIdentity.getMSPID(),
            status: 'ISSUED',
        };
        await ctx.stub.putState(key, Buffer.from(JSON.stringify(credit)));
        await ctx.stub.putState(originKey, Buffer.from(creditId));
        await ctx.stub.putState(registryKey, Buffer.from(creditId));
        return credit;
    }

    async TransferCredit(ctx, creditId, newOwnerMsp) {
        const credit = await this.ReadCredit(ctx, creditId);
        if (credit.status === 'RETIRED') {
            throw new Error(`Credit ${creditId} is retired`);
        }
        if (ctx.clientIdentity.getMSPID() !== credit.ownerMsp) {
            throw new Error('Only the current owner organization can transfer this credit');
        }
        if (!['Org1MSP', 'Org2MSP'].includes(newOwnerMsp) || newOwnerMsp === credit.ownerMsp) {
            throw new Error('Recipient must be a different participating organization');
        }

        credit.ownerMsp = newOwnerMsp;
        credit.status = 'TRANSFERRED';
        credit.lastTransferTxId = ctx.stub.getTxID();
        const key = ctx.stub.createCompositeKey('credit', [creditId]);
        await ctx.stub.putState(key, Buffer.from(JSON.stringify(credit)));
        return credit;
    }

    async RetireCredit(ctx, creditId) {
        const credit = await this.ReadCredit(ctx, creditId);
        if (credit.status === 'RETIRED') {
            throw new Error(`Credit ${creditId} is already retired`);
        }
        if (ctx.clientIdentity.getMSPID() !== credit.ownerMsp) {
            throw new Error('Only the current owner organization can retire this credit');
        }

        credit.status = 'RETIRED';
        credit.retirementTxId = ctx.stub.getTxID();
        const key = ctx.stub.createCompositeKey('credit', [creditId]);
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
