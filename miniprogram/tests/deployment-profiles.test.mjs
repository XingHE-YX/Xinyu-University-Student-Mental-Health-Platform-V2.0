import assert from 'node:assert/strict'
import test from 'node:test'

import { deploymentProfileForAppId } from '../config/deployment-profiles.ts'

test('selects the deployed demo API from the running mini-program AppID', () => {
  assert.deepEqual(deploymentProfileForAppId('wx22f399558d68bc7f'), {
    apiBaseUrl:
      'https://xinyu-v2-demo-d3g8qbyfu11a452ff-1489915847.ap-shanghai.app.tcloudbase.com/api/v1',
    cloudbaseEnvId: 'xinyu-v2-demo-d3g8qbyfu11a452ff',
    environmentKind: 'demo',
  })
})

test('keeps unknown AppIDs unconfigured instead of falling back to demo', () => {
  assert.equal(deploymentProfileForAppId('wx-unknown'), null)
  assert.equal(deploymentProfileForAppId(''), null)
})
