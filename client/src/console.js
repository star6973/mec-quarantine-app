import './Console.scss';
import { useState, useEffect } from "react";
import Keypad from './components/Keypad';

function Console() {
    const [keyList, setKeyList] = useState();
    
    useEffect(() => {

    }, [])

    return (
        <Keypad />
    )
}

export default Console;