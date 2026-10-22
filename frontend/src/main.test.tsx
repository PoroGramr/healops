import {describe,it,expect} from 'vitest'
import {render,screen} from '@testing-library/react'
import {App} from './main'

describe('dashboard',()=>{
 it('requires an administrator token before showing data',()=>{sessionStorage.clear();render(<App/>);expect(screen.getByText('Connect to your local control plane')).toBeTruthy()})
})
