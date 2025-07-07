import re
import statistics
from datetime import datetime
from typing import Any, Dict, List, Union, Callable
from collections import Counter


class EvalExecutor:
    """基于名称匹配的 Eval 函数系统"""

    def __init__(self):
        self.eval_functions = {}
        self._register_default_functions()

    def _register_default_functions(self):
        """注册默认的 eval 函数"""

        def celestia_eval(manager, query, evaluate):
            info = manager.status_dump(query)
            for eval_item in evaluate:
                hkey: Callable = lambda info: info[eval_item["key"]]
                pred: Callable = lambda left, right: left == right

                if hasattr(key_eval := eval(eval_item["key"]), "__call__"):
                    hkey = key_eval
                if "pred" in eval_item:
                    pred = eval(eval_item["pred"])
                if not pred(hkey(info), eval_item["value"]):
                    print(f"Evaluation failed at {eval_item['type']} of {eval_item['key']}.")
                    return False
            return True
        # 字符串处理
        def chimerax_eval(manager, evaluate):
            current_states = manager.states_dump()
            for eval_item in evaluate:
                eval_type = eval_item["type"]
                # eval_func is not bound method because of the decorator factory?
                eval_func = getattr(self, f"_eval_{eval_type}")
                if not eval_func(eval_item, current_states):
                    print(f"Evaluation failed at {eval_type} of {eval_item['key']}.")
                    return False
            return True
        # 数组操作
        def array_processor(arr: List[Union[int, float]], operation: str, value: Any = None) -> Union[float, List, str]:
            try:
                operations = {
                    'sum': lambda a, v: sum(a),
                    'average': lambda a, v: statistics.mean(a),
                    'median': lambda a, v: statistics.median(a),
                    'mode': lambda a, v: statistics.mode(a),
                    'max': lambda a, v: max(a),
                    'min': lambda a, v: min(a),
                    'sort': lambda a, v: sorted(a),
                    'reverse': lambda a, v: list(reversed(a)),
                    'unique': lambda a, v: list(set(a)),
                    'filter_greater': lambda a, v: [x for x in a if x > v] if v is not None else 'Error: No filter value',
                    'filter_less': lambda a, v: [x for x in a if x < v] if v is not None else 'Error: No filter value',
                    'count': lambda a, v: len(a),
                    'slice': lambda a, v: a[v['start']:v['end']] if isinstance(v, dict) else 'Error: Invalid slice value'
                }
                return operations.get(operation, lambda a, v: 'Error: Unknown array operation')(arr, value)
            except Exception as e:
                return f'Error: {str(e)}'

        # 用户验证
        def user_validator(user_data: Dict[str, Any]) -> Dict[str, Any]:
            errors = []

            username = user_data.get('username', '')
            email = user_data.get('email', '')
            age = user_data.get('age', 0)
            password = user_data.get('password', '')

            # 用户名验证
            if not username or len(username) < 3:
                errors.append('Username must be at least 3 characters')
            elif len(username) > 20:
                errors.append('Username must be less than 20 characters')

            # 邮箱验证
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not email or not re.match(email_pattern, email):
                errors.append('Invalid email format')

            # 年龄验证
            if not isinstance(age, int) or age < 0:
                errors.append('Age must be a positive integer')
            elif age < 18:
                errors.append('User must be at least 18 years old')

            # 密码验证
            if password:
                if len(password) < 8:
                    errors.append('Password must be at least 8 characters')
                if not re.search(r'[A-Z]', password):
                    errors.append('Password must contain at least one uppercase letter')
                if not re.search(r'[a-z]', password):
                    errors.append('Password must contain at least one lowercase letter')
                if not re.search(r'\d', password):
                    errors.append('Password must contain at least one digit')

            return {
                'is_valid': len(errors) == 0,
                'errors': errors,
                'user_data': user_data
            }

        # 日期处理
        def date_processor(date_input: Union[str, datetime], format_type: str) -> Union[str, int]:
            try:
                if isinstance(date_input, str):
                    # 尝试解析多种日期格式
                    date_formats = ['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%Y-%m-%d %H:%M:%S']
                    date_obj = None
                    for fmt in date_formats:
                        try:
                            date_obj = datetime.strptime(date_input, fmt)
                            break
                        except ValueError:
                            continue
                    if date_obj is None:
                        return 'Error: Unable to parse date'
                else:
                    date_obj = date_input

                formats = {
                    'yyyy-mm-dd': lambda d: d.strftime('%Y-%m-%d'),
                    'dd/mm/yyyy': lambda d: d.strftime('%d/%m/%Y'),
                    'mm/dd/yyyy': lambda d: d.strftime('%m/%d/%Y'),
                    'timestamp': lambda d: int(d.timestamp()),
                    'readable': lambda d: d.strftime('%Y年%m月%d日'),
                    'weekday': lambda d: d.strftime('%A'),
                    'month_name': lambda d: d.strftime('%B'),
                    'iso': lambda d: d.isoformat(),
                    'year': lambda d: d.year,
                    'month': lambda d: d.month,
                    'day': lambda d: d.day
                }

                return formats.get(format_type, lambda d: str(d))(date_obj)
            except Exception as e:
                return f'Error: {str(e)}'

        # 数据分析
        def data_analyzer(data: List[Any], analysis_type: str) -> Union[Dict, List, int, str]:
            try:
                analyses = {
                    'count': lambda d: len(d),
                    'unique': lambda d: list(set(d)),
                    'unique_count': lambda d: len(set(d)),
                    'frequency': lambda d: dict(Counter(d)),
                    'most_common': lambda d: Counter(d).most_common(),
                    'group_by_type': lambda d: self._group_by_type(d),
                    'statistics': lambda d: self._get_statistics(d) if all(isinstance(x, (int, float)) for x in d) else 'Error: Data must be numeric for statistics'
                }
                return analyses.get(analysis_type, lambda d: 'Error: Unknown analysis type')(data)
            except Exception as e:
                return f'Error: {str(e)}'

        # 文本分析
        def text_analyzer(text: str, analysis_type: str) -> Union[Dict, List, int, str]:
            try:
                analyses = {
                    'word_count': lambda t: len(t.split()),
                    'char_count': lambda t: len(t),
                    'sentence_count': lambda t: len([s for s in re.split(r'[.!?]+', t) if s.strip()]),
                    'paragraph_count': lambda t: len([p for p in t.split('\n\n') if p.strip()]),
                    'word_frequency': lambda t: dict(Counter(t.lower().split())),
                    'char_frequency': lambda t: dict(Counter(t.lower())),
                    'extract_emails': lambda t: re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', t),
                    'extract_urls': lambda t: re.findall(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', t),
                    'extract_numbers': lambda t: [float(x) for x in re.findall(r'-?\d+\.?\d*', t)],
                    'readability_score': lambda t: self._calculate_readability(t)
                }
                return analyses.get(analysis_type, lambda t: 'Error: Unknown text analysis type')(text)
            except Exception as e:
                return f'Error: {str(e)}'

        # 注册所有函数
        self.eval_functions.update({
            'Celestia': celestia_eval,
            'string_processor': string_processor,
            'array_processor': array_processor,
            'user_validator': user_validator,
            'date_processor': date_processor,
            'data_analyzer': data_analyzer,
            'text_analyzer': text_analyzer
        })

    def _group_by_type(self, data: List[Any]) -> Dict[str, List]:
        """按数据类型分组"""
        groups = {}
        for item in data:
            type_name = type(item).__name__
            if type_name not in groups:
                groups[type_name] = []
            groups[type_name].append(item)
        return groups

    def _get_statistics(self, data: List[Union[int, float]]) -> Dict[str, float]:
        """获取数值数据的统计信息"""
        return {
            'count': len(data),
            'sum': sum(data),
            'mean': statistics.mean(data),
            'median': statistics.median(data),
            'mode': statistics.mode(data) if len(set(data)) < len(data) else 'No mode',
            'std_dev': statistics.stdev(data) if len(data) > 1 else 0,
            'variance': statistics.variance(data) if len(data) > 1 else 0,
            'min': min(data),
            'max': max(data),
            'range': max(data) - min(data)
        }

    def _calculate_readability(self, text: str) -> Dict[str, float]:
        """计算文本可读性得分"""
        words = text.split()
        sentences = len([s for s in re.split(r'[.!?]+', text) if s.strip()])
        syllables = sum([self._count_syllables(word) for word in words])

        if sentences == 0 or len(words) == 0:
            return {'flesch_score': 0, 'grade_level': 0}

        # Flesch Reading Ease Score
        flesch_score = 206.835 - (1.015 * len(words) / sentences) - (84.6 * syllables / len(words))

        # Flesch-Kincaid Grade Level
        grade_level = (0.39 * len(words) / sentences) + (11.8 * syllables / len(words)) - 15.59

        return {
            'flesch_score': round(flesch_score, 2),
            'grade_level': round(grade_level, 2),
            'word_count': len(words),
            'sentence_count': sentences,
            'syllable_count': syllables
        }

    def _count_syllables(self, word: str) -> int:
        """估算单词的音节数"""
        word = word.lower()
        vowels = 'aeiouy'
        syllable_count = 0
        previous_was_vowel = False

        for char in word:
            if char in vowels:
                if not previous_was_vowel:
                    syllable_count += 1
                previous_was_vowel = True
            else:
                previous_was_vowel = False

        if word.endswith('e'):
            syllable_count -= 1

        return max(1, syllable_count)

    def execute_eval(self, name: str, *args, **kwargs) -> Dict[str, Any]:
        """执行指定名称的 eval 函数"""
        if name not in self.eval_functions:
            return {
                'success': False,
                'error': f"Function '{name}' not found",
                'available_functions': list(self.eval_functions.keys())
            }

        try:
            result = self.eval_functions[name](*args, **kwargs)
            return {
                'success': True,
                'result': result,
                'executed_function': name
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'executed_function': name
            }

    def get_available_functions(self) -> List[Dict[str, str]]:
        """获取所有可用函数的信息"""
        descriptions = {
            'math_calculator': '数学计算 - 参数: (a, b, operation)',
            'string_processor': '字符串处理 - 参数: (text, action, value=None)',
            'array_processor': '数组操作 - 参数: (arr, operation, value=None)',
            'user_validator': '用户验证 - 参数: (user_data)',
            'date_processor': '日期处理 - 参数: (date_input, format_type)',
            'data_analyzer': '数据分析 - 参数: (data, analysis_type)',
            'text_analyzer': '文本分析 - 参数: (text, analysis_type)'
        }

        return [
            {
                'name': name,
                'description': descriptions.get(name, '无描述')
            }
            for name in self.eval_functions.keys()
        ]

    def add_eval_function(self, name: str, func: Callable, description: str = '') -> None:
        """动态添加新的 eval 函数"""
        if not callable(func):
            raise ValueError('参数 func 必须是一个可调用对象')

        self.eval_functions[name] = func
        print(f"函数 '{name}' 添加成功")

    def remove_eval_function(self, name: str) -> bool:
        """移除 eval 函数"""
        if name in self.eval_functions:
            del self.eval_functions[name]
            print(f"函数 '{name}' 移除成功")
            return True
        return False


# 使用示例
def main():
    # 创建 eval 系统实例
    eval_system = EvalSystem()

    print('=== Python Eval 函数系统使用示例 ===\n')

    # 1. 数学计算
    print('1. 数学计算:')
    print(eval_system.execute_eval('math_calculator', 10, 5, 'add'))
    print(eval_system.execute_eval('math_calculator', 10, 3, 'power'))

    # 2. 字符串处理
    print('\n2. 字符串处理:')
    print(eval_system.execute_eval('string_processor', 'Hello World', 'uppercase'))
    print(eval_system.execute_eval('string_processor', 'Hello World', 'replace', {'from': 'World', 'to': 'Python'}))
    print(eval_system.execute_eval('string_processor', 'Python Programming', 'split', ' '))

    # 3. 数组操作
    print('\n3. 数组操作:')
    print(eval_system.execute_eval('array_processor', [1, 2, 3, 4, 5], 'sum'))
    print(eval_system.execute_eval('array_processor', [5, 2, 8, 1, 9, 2, 5], 'unique'))
    print(eval_system.execute_eval('array_processor', [1, 2, 3, 4, 5], 'filter_greater', 3))

    # 4. 用户验证
    print('\n4. 用户验证:')
    valid_user = {
        'username': 'john_doe',
        'email': 'john@example.com',
        'age': 25,
        'password': 'SecurePass123'
    }
    print(eval_system.execute_eval('user_validator', valid_user))

    invalid_user = {
        'username': 'jo',
        'email': 'invalid-email',
        'age': 16,
        'password': 'weak'
    }
    print(eval_system.execute_eval('user_validator', invalid_user))

    # 5. 日期处理
    print('\n5. 日期处理:')
    print(eval_system.execute_eval('date_processor', '2024-03-15', 'dd/mm/yyyy'))
    print(eval_system.execute_eval('date_processor', '2024-03-15', 'readable'))
    print(eval_system.execute_eval('date_processor', '2024-03-15', 'weekday'))

    # 6. 数据分析
    print('\n6. 数据分析:')
    sample_data = ['apple', 'banana', 'apple', 'orange', 'banana', 'apple']
    print(eval_system.execute_eval('data_analyzer', sample_data, 'frequency'))
    print(eval_system.execute_eval('data_analyzer', sample_data, 'most_common'))

    # 7. 文本分析
    print('\n7. 文本分析:')
    sample_text = "Python is a powerful programming language. It's easy to learn and use."
    print(eval_system.execute_eval('text_analyzer', sample_text, 'word_count'))
    print(eval_system.execute_eval('text_analyzer', sample_text, 'word_frequency'))

    # 8. 错误处理示例
    print('\n8. 错误处理:')
    print(eval_system.execute_eval('non_existent_function', 'test'))

    # 9. 查看所有可用函数
    print('\n9. 所有可用函数:')
    for func_info in eval_system.get_available_functions():
        print(f"- {func_info['name']}: {func_info['description']}")

    # 10. 动态添加新函数示例
    print('\n10. 动态添加新函数:')
    def custom_greeting(name: str, language: str = 'zh') -> str:
        greetings = {
            'zh': f'你好，{name}！',
            'en': f'Hello, {name}!',
            'es': f'¡Hola, {name}!',
            'fr': f'Bonjour, {name}!'
        }
        return greetings.get(language, greetings['en'])

    eval_system.add_eval_function('custom_greeting', custom_greeting, '自定义问候语')
    print(eval_system.execute_eval('custom_greeting', '张三', 'zh'))
    print(eval_system.execute_eval('custom_greeting', 'John', 'en'))


if __name__ == '__main__':
    main()