import axios from 'axios'

const request = axios.create({
    baseURL: '/api',
    timeout: 10_000,
})

export default request



