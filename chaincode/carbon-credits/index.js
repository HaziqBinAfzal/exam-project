'use strict';

const { Contract } = require('fabric-contract-api');

class CarbonCredits extends Contract {
    async AnchorEvidence(ctx, bundleId, evidenceSha256) {
        if (ctx.clientIdentity.getMSPID() !== 'Org1MSP') {
            throw new Error('Only the issuer organization can anchor evidence');
        }
        if (!/^[A-Za-z0-9_-]{1,64}$/.test(bundleId)) {
            throw new Error('Invalid bundle ID');
        }
        if (!/^[a-f0-9]{64}$/.test(evidenceSha256)) {
            throw new Error('Expected a lowercase SHA-256 evidence fingerprint');
        }

        const key = ctx.stub.createCompositeKey('evidence-anchor', [bundleId]);
        const existing = await ctx.stub.getState(key);
        if (existing.length > 0) {
            const anchor = JSON.parse(existing.toString('utf8'));
            if (anchor.evidenceSha256 !== evidenceSha256) {
                throw new Error(`Bundle ${bundleId} already has a different fingerprint`);
            }
            return anchor;
        }

        const anchor = {
            bundleId,
            evidenceSha256,
            issuerMsp: ctx.clientIdentity.getMSPID(),
            anchorTxId: ctx.stub.getTxID(),
        };
        await ctx.stub.putState(key, Buffer.from(JSON.stringify(anchor)));
        return anchor;
    }

    async ReadEvidenceAnchor(ctx, bundleId) {
        if (!/^[A-Za-z0-9_-]{1,64}$/.test(bundleId)) {
            throw new Error('Invalid bundle ID');
        }

        const key = ctx.stub.createCompositeKey('evidence-anchor', [bundleId]);
        const record = await ctx.stub.getState(key);
        if (record.length === 0) {
            throw new Error(`Evidence anchor ${bundleId} was not found`);
        }
        return JSON.parse(record.toString('utf8'));
    }

    async ApproveOrigin(ctx, originId, registry, registryRef, quantityText, methodology, evidenceSha256) {
        if (ctx.clientIdentity.getMSPID() !== 'Org2MSP') {
            throw new Error('Only the verifier organization can approve origins');
        }
        if (!['REGISTRY-A', 'REGISTRY-B'].includes(registry) ||
            !/^[A-Z0-9-]{1,64}$/.test(originId) ||
            !/^[A-Z0-9-]{1,64}$/.test(registryRef)) {
            throw new Error('Invalid registry, reference, or origin');
        }

        const quantity = Number(quantityText);
        if (!/^[1-9][0-9]*$/.test(quantityText) || !Number.isSafeInteger(quantity)) {
            throw new Error('Quantity must be a positive whole number');
        }
        if (methodology !== 'DEMO-MRV-V1') {
            throw new Error('Unsupported verification methodology');
        }
        if (!/^[a-f0-9]{64}$/.test(evidenceSha256)) {
            throw new Error('Expected a lowercase SHA-256 evidence fingerprint');
        }

        const key = ctx.stub.createCompositeKey('origin-approval', [originId]);
        if ((await ctx.stub.getState(key)).length > 0) {
            throw new Error(`Origin ${originId} already has an approval`);
        }

        const approval = {
            originId,
            registry,
            registryRef,
            quantityTonnesCO2e: quantity,
            methodology,
            evidenceSha256,
            verifierMsp: ctx.clientIdentity.getMSPID(),
            approvalTxId: ctx.stub.getTxID(),
        };
        await ctx.stub.putState(key, Buffer.from(JSON.stringify(approval)));
        return approval;
    }

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

        const approvalKey = ctx.stub.createCompositeKey('origin-approval', [originId]);
        const approvalBytes = await ctx.stub.getState(approvalKey);
        if (approvalBytes.length === 0) {
            throw new Error(`Origin ${originId} has no verifier approval`);
        }

        const approval = JSON.parse(approvalBytes.toString('utf8'));
        if (approval.registry !== registry || approval.registryRef !== registryRef ||
            approval.quantityTonnesCO2e !== quantity) {
            throw new Error(`Issuance does not match the approval for ${originId}`);
        }

        const credit = {
            creditId,
            registry,
            registryRef,
            originId,
            verification: approval,
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
