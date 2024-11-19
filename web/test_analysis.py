from analysis.crypto_analyzer import CryptoAnalyzer


def main():
    try:
        analyzer = CryptoAnalyzer('BNBUSDT')
        result = analyzer.analyze()
        print(result)
    except Exception as e:
        print(f'Error: {str(e)}')


if __name__ == '__main__':
    main()
