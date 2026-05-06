"""
dict_management.py — 사용자 사전 관리 예제

실행:
    python examples/dict_management.py register
    python examples/dict_management.py list
    python examples/dict_management.py test --domain my-domain --text "청소년참여위원회 정책"
"""
import argparse
from bareun_pipeline import DictManager


def main():
    parser = argparse.ArgumentParser(description="bareun 사용자 사전 관리 예제")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("register", help="예제 사전 등록")
    sub.add_parser("list",     help="등록된 사전 목록")

    p_test = sub.add_parser("test", help="단문 테스트")
    p_test.add_argument("--domain", default="example-domain")
    p_test.add_argument("--text",   default="청소년참여위원회에서 학교폭력예방 정책을 논의했다.")

    args = parser.parse_args()

    dm = DictManager.from_env() if hasattr(DictManager, "from_env") else DictManager()

    if args.cmd == "register":
        dm.register(
            domain       = "example-domain",
            np_set       = ["청소년참여위원회", "학교폭력대책위원회", "여성가족부"],
            cp_set       = ["학교폭력예방", "청소년상담복지", "위기청소년"],
            cp_caret_set = ["학교^폭력", "청소년^정책"],
        )

    elif args.cmd == "list":
        dm.list_domains()

    elif args.cmd == "test":
        dm.test(domain=args.domain, text=args.text)


if __name__ == "__main__":
    main()
